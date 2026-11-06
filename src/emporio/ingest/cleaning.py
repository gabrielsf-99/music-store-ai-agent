"""Parse raw CSV rows into typed records ready to be loaded."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

Row = dict[str, str]
Record = dict[str, Any]

PRODUCT_STATUSES = {"active", "discontinued", "coming_soon"}
ORDER_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
SIMPLE_PAYMENT_METHODS = {"pix", "debit", "boleto"}
MAX_INSTALLMENTS = 12

_CREDIT_PATTERN = re.compile(r"credit_(\d{1,2})x")
_CENTS = Decimal("0.01")


class DataValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Dataset:
    categories: list[Record]
    products: list[Record]
    promotions: list[Record]
    customers: list[Record]
    orders: list[Record]
    order_items: list[Record]


def text(value: str | None, field: str, *, required: bool = True) -> str | None:
    value = (value or "").strip()
    if not value:
        if required:
            raise DataValidationError(f"'{field}' is empty")
        return None
    return value


def parse_int(value: str, field: str) -> int:
    try:
        return int(text(value, field))
    except ValueError as exc:
        raise DataValidationError(f"'{field}' is not an integer: {value!r}") from exc


def parse_money(value: str, field: str) -> Decimal:
    try:
        amount = Decimal(text(value, field))
    except InvalidOperation as exc:
        raise DataValidationError(f"'{field}' is not a number: {value!r}") from exc
    if amount < 0:
        raise DataValidationError(f"'{field}' is negative: {value!r}")
    return amount.quantize(_CENTS)


def parse_date(value: str, field: str, *, required: bool = True) -> date | None:
    raw = text(value, field, required=required)
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise DataValidationError(f"'{field}' is not a YYYY-MM-DD date: {value!r}") from exc


def parse_flag(value: str, field: str) -> bool:
    raw = text(value, field)
    if raw not in {"0", "1"}:
        raise DataValidationError(f"'{field}' must be 0 or 1: {value!r}")
    return raw == "1"


def parse_choice(value: str, field: str, choices: set[str]) -> str:
    raw = text(value, field)
    if raw not in choices:
        raise DataValidationError(f"'{field}' must be one of {sorted(choices)}: {value!r}")
    return raw


def parse_specs(value: str) -> dict:
    raw = text(value, "specs", required=False)
    if raw is None:
        return {}
    try:
        specs = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"'specs' is not valid JSON: {raw[:60]!r}") from exc
    if not isinstance(specs, dict):
        raise DataValidationError("'specs' must be a JSON object")
    return specs


def normalize_email(value: str) -> str:
    email = text(value, "email").lower()
    if "@" not in email:
        raise DataValidationError(f"'email' is invalid: {value!r}")
    return email


def phone_digits(value: str) -> str:
    digits = re.sub(r"\D", "", text(value, "phone"))
    if len(digits) not in (10, 11):
        raise DataValidationError(f"'phone' must have 10 or 11 digits: {value!r}")
    return digits


def parse_payment_method(value: str) -> tuple[str, int | None]:
    """`pix` -> ("pix", None); `credit_6x` -> ("credit_card", 6)."""
    raw = text(value, "payment_method").lower()
    if raw in SIMPLE_PAYMENT_METHODS:
        return raw, None
    match = _CREDIT_PATTERN.fullmatch(raw)
    if match and 1 <= int(match.group(1)) <= MAX_INSTALLMENTS:
        return "credit_card", int(match.group(1))
    raise DataValidationError(f"'payment_method' is not recognized: {value!r}")


def clean_category(row: Row) -> Record:
    return {
        "category_id": parse_int(row.get("category_id"), "category_id"),
        "name": text(row.get("name"), "name"),
        "description": text(row.get("description"), "description", required=False),
    }


def clean_product(row: Row) -> Record:
    return {
        "product_id": parse_int(row.get("product_id"), "product_id"),
        "category_id": parse_int(row.get("category_id"), "category_id"),
        "name": text(row.get("name"), "name"),
        "description": text(row.get("description"), "description", required=False),
        "price_brl": parse_money(row.get("price_brl"), "price_brl"),
        "stock_quantity": parse_int(row.get("stock_quantity"), "stock_quantity"),
        "status": parse_choice(row.get("status"), "status", PRODUCT_STATUSES),
        "specs": parse_specs(row.get("specs")),
        "created_at": parse_date(row.get("created_at"), "created_at", required=False),
    }


def clean_promotion(row: Row) -> Record:
    discount = parse_int(row.get("discount_percent"), "discount_percent")
    if not 1 <= discount <= 100:
        raise DataValidationError(f"'discount_percent' out of range: {discount}")
    return {
        "promotion_id": parse_int(row.get("promotion_id"), "promotion_id"),
        "product_id": parse_int(row.get("product_id"), "product_id"),
        "discount_percent": discount,
        "description": text(row.get("description"), "description", required=False),
        "is_active": parse_flag(row.get("is_active"), "is_active"),
    }


def clean_customer(row: Row) -> Record:
    return {
        "customer_id": parse_int(row.get("customer_id"), "customer_id"),
        "name": text(row.get("name"), "name"),
        "phone": text(row.get("phone"), "phone"),
        "phone_digits": phone_digits(row.get("phone")),
        "email": normalize_email(row.get("email")),
        "city": text(row.get("city"), "city", required=False),
    }


def clean_order(row: Row) -> Record:
    method, installments = parse_payment_method(row.get("payment_method"))
    return {
        "order_id": parse_int(row.get("order_id"), "order_id"),
        "customer_id": parse_int(row.get("customer_id"), "customer_id"),
        "order_date": parse_date(row.get("order_date"), "order_date"),
        "status": parse_choice(row.get("status"), "status", ORDER_STATUSES),
        "total_brl": parse_money(row.get("total_brl"), "total_brl"),
        "payment_method": method,
        "installments": installments,
        "tracking_code": text(row.get("tracking_code"), "tracking_code", required=False),
        "estimated_delivery": parse_date(
            row.get("estimated_delivery"), "estimated_delivery", required=False
        ),
        "notes": text(row.get("notes"), "notes", required=False),
    }


def clean_order_item(row: Row) -> Record:
    quantity = parse_int(row.get("quantity"), "quantity")
    if quantity <= 0:
        raise DataValidationError(f"'quantity' must be positive: {quantity}")
    return {
        "order_id": parse_int(row.get("order_id"), "order_id"),
        "product_id": parse_int(row.get("product_id"), "product_id"),
        "quantity": quantity,
    }


def clean_rows(source: str, rows: list[Row], clean: Callable[[Row], Record]) -> list[Record]:
    """Apply `clean` to every row, prefixing errors with `file:line`."""
    records = []
    for line, row in enumerate(rows, start=2):  # line 1 is the header
        try:
            records.append(clean(row))
        except DataValidationError as exc:
            raise DataValidationError(f"{source}:{line}: {exc}") from exc
    return records
