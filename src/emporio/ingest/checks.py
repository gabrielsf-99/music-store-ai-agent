"""Dataset-level checks: integrity errors abort the load, inconsistencies become warnings."""

from collections import Counter, defaultdict
from decimal import Decimal

from emporio.ingest.cleaning import Dataset, DataValidationError, Record


def _duplicates(records: list[Record], *keys: str) -> list[tuple]:
    counts = Counter(tuple(record[key] for key in keys) for record in records)
    return [key for key, count in counts.items() if count > 1]


def _missing_refs(records: list[Record], field: str, valid_ids: set[int]) -> list[int]:
    return sorted({record[field] for record in records} - valid_ids)


def check_integrity(data: Dataset) -> None:
    """Raise if primary keys repeat or references point to missing rows."""
    errors = []

    primary_keys = [
        ("categories.csv", data.categories, ("category_id",)),
        ("products.csv", data.products, ("product_id",)),
        ("promotions.csv", data.promotions, ("promotion_id",)),
        ("customers.csv", data.customers, ("customer_id",)),
        ("orders.csv", data.orders, ("order_id",)),
        ("order_items.csv", data.order_items, ("order_id", "product_id")),
    ]
    for source, records, keys in primary_keys:
        if duplicated := _duplicates(records, *keys):
            errors.append(f"{source}: duplicated {', '.join(keys)}: {duplicated}")

    category_ids = {c["category_id"] for c in data.categories}
    product_ids = {p["product_id"] for p in data.products}
    customer_ids = {c["customer_id"] for c in data.customers}
    order_ids = {o["order_id"] for o in data.orders}

    references = [
        ("products.csv", data.products, "category_id", category_ids),
        ("promotions.csv", data.promotions, "product_id", product_ids),
        ("orders.csv", data.orders, "customer_id", customer_ids),
        ("order_items.csv", data.order_items, "order_id", order_ids),
        ("order_items.csv", data.order_items, "product_id", product_ids),
    ]
    for source, records, field, valid_ids in references:
        if missing := _missing_refs(records, field, valid_ids):
            errors.append(f"{source}: unknown {field}: {missing}")

    if orders_without_items := sorted(order_ids - {i["order_id"] for i in data.order_items}):
        errors.append(f"orders.csv: orders without items: {orders_without_items}")

    if errors:
        raise DataValidationError("\n".join(errors))


def find_inconsistencies(data: Dataset) -> list[str]:
    """Data that loads fine but deserves attention (see ADR 0001, section 3)."""
    warnings = []
    products = {p["product_id"]: p for p in data.products}

    items_by_order = defaultdict(list)
    for item in data.order_items:
        items_by_order[item["order_id"]].append(item)

    for order in data.orders:
        items = items_by_order[order["order_id"]]
        expected = sum(
            (products[i["product_id"]]["price_brl"] * i["quantity"] for i in items), Decimal(0)
        )
        if expected != order["total_brl"]:
            warnings.append(
                f"order {order['order_id']}: total {order['total_brl']} differs from "
                f"current catalog prices {expected}"
            )
        for item in items:
            status = products[item["product_id"]]["status"]
            if status != "active":
                warnings.append(
                    f"order {order['order_id']}: contains product {item['product_id']} "
                    f"with status '{status}'"
                )

    active_by_product = Counter(p["product_id"] for p in data.promotions if p["is_active"])
    for product_id, count in sorted(active_by_product.items()):
        if count > 1:
            warnings.append(
                f"product {product_id}: {count} active promotions (highest discount applies)"
            )

    customers_by_email = defaultdict(list)
    for customer in data.customers:
        customers_by_email[customer["email"]].append(customer["customer_id"])
    for email, ids in sorted(customers_by_email.items()):
        if len(ids) > 1:
            warnings.append(f"customers {ids} share the email {email}")

    return warnings
