"""Order lookup with identity verification (LGPD).

An order is returned only when the e-mail or phone given matches the customer *of that order*.
Failures return None without saying whether the order exists.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from emporio.domain.returns import Deadline, return_deadlines

_ORDER_QUERY = """
SELECT o.order_id, o.status, o.order_date, o.total_brl, o.payment_method, o.installments,
       o.tracking_code, o.estimated_delivery, o.notes,
       c.name AS customer_name, c.email, c.phone_digits
FROM orders o
JOIN customers c USING (customer_id)
WHERE o.order_id = %s
"""

_ITEMS_QUERY = """
SELECT p.name, i.quantity
FROM order_items i
JOIN products p USING (product_id)
WHERE i.order_id = %s
ORDER BY p.name
"""

BRAZIL_COUNTRY_CODE = "55"


@dataclass(frozen=True)
class OrderItem:
    name: str
    quantity: int


@dataclass(frozen=True)
class OrderStatus:
    order_id: int
    customer_first_name: str
    status: str
    order_date: date
    total: Decimal
    payment_method: str
    installments: int | None
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
    items: list[OrderItem]
    deadlines: list[Deadline] = field(default_factory=list)


def normalize_phone(value: str) -> str:
    """Digits only, without the +55 country code."""
    digits = re.sub(r"\D", "", value)
    if len(digits) in (12, 13) and digits.startswith(BRAZIL_COUNTRY_CODE):
        digits = digits[len(BRAZIL_COUNTRY_CODE) :]
    return digits


def contact_matches(contact: str, email: str, phone_digits: str) -> bool:
    contact = contact.strip()
    if "@" in contact:
        return contact.lower() == email.lower()
    digits = normalize_phone(contact)
    return len(digits) in (10, 11) and digits == phone_digits


def get_order_status(
    conn: psycopg.Connection, order_id: int, contact: str, today: date
) -> OrderStatus | None:
    with conn.cursor(row_factory=dict_row) as cur:
        order = cur.execute(_ORDER_QUERY, (order_id,)).fetchone()
        if order is None or not contact_matches(contact, order["email"], order["phone_digits"]):
            return None
        items = [OrderItem(**row) for row in cur.execute(_ITEMS_QUERY, (order_id,)).fetchall()]

    deadlines = []
    if order["status"] == "delivered" and order["estimated_delivery"]:
        deadlines = return_deadlines(order["order_date"], order["estimated_delivery"], today)

    return OrderStatus(
        order_id=order["order_id"],
        customer_first_name=order["customer_name"].split()[0],
        status=order["status"],
        order_date=order["order_date"],
        total=order["total_brl"],
        payment_method=order["payment_method"],
        installments=order["installments"],
        tracking_code=order["tracking_code"],
        estimated_delivery=order["estimated_delivery"],
        notes=order["notes"],
        items=items,
        deadlines=deadlines,
    )
