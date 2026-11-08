"""Order lookup against the fixture dataset.

Fixture customers: 1 Ana (ana.exemplo@example.com, (67) 99999-0001),
2 Bruno and 3 Carla (both compartilhado@example.com; Carla has a landline).
Orders: 1 delivered (Ana), 2 shipped (Bruno), 3 pending (Carla), 4 cancelled (Ana).
"""

from datetime import date

import pytest

from emporio.tools.orders import get_order_status

pytestmark = pytest.mark.integration

TODAY = date(2026, 1, 20)


@pytest.mark.parametrize(
    "contact", ["ana.exemplo@example.com", "ANA.EXEMPLO@example.com", "+55 (67) 99999-0001"]
)
def test_order_is_returned_when_contact_matches(loaded_conn, contact):
    order = get_order_status(loaded_conn, 1, contact, TODAY)

    assert order.order_id == 1
    assert order.customer_first_name == "Ana"
    assert order.status == "delivered"
    assert [(i.name, i.quantity) for i in order.items] == [("Violão Aurora Nylon Natural", 1)]


@pytest.mark.parametrize(
    ("order_id", "contact"),
    [
        (1, "compartilhado@example.com"),  # another customer's e-mail
        (1, "(67) 99999-0002"),  # another customer's phone
        (999, "ana.exemplo@example.com"),  # order does not exist
    ],
)
def test_lookup_fails_without_revealing_why(loaded_conn, order_id, contact):
    assert get_order_status(loaded_conn, order_id, contact, TODAY) is None


def test_landline_phone_is_accepted(loaded_conn):
    assert get_order_status(loaded_conn, 3, "(67) 3333-0003", TODAY).status == "pending"


def test_delivered_order_has_return_deadlines(loaded_conn):
    order = get_order_status(loaded_conn, 1, "ana.exemplo@example.com", TODAY)
    withdrawal = next(d for d in order.deadlines if d.name == "arrependimento")

    assert withdrawal.until == date(2026, 1, 22)
    assert withdrawal.is_open


def test_order_in_transit_has_no_deadlines_yet(loaded_conn):
    order = get_order_status(loaded_conn, 2, "compartilhado@example.com", TODAY)

    assert order.status == "shipped"
    assert order.tracking_code == "BRBB2222222BR"
    assert (order.payment_method, order.installments) == ("credit_card", 12)
    assert order.deadlines == []


def test_cancelled_order_keeps_reason(loaded_conn):
    order = get_order_status(loaded_conn, 4, "ana.exemplo@example.com", TODAY)

    assert order.status == "cancelled"
    assert order.notes == "Pedido cancelado pelo cliente"
