from datetime import date
from decimal import Decimal

from emporio.agent.tools import order_to_dict, payment_label
from emporio.domain.returns import return_deadlines
from emporio.tools.orders import OrderItem, OrderStatus


def make_order(**overrides) -> OrderStatus:
    fields = {
        "order_id": 1,
        "customer_first_name": "Ana",
        "status": "delivered",
        "order_date": date(2026, 1, 10),
        "total": Decimal("499.90"),
        "payment_method": "pix",
        "installments": None,
        "tracking_code": "BRAA1111111BR",
        "estimated_delivery": date(2026, 1, 15),
        "notes": None,
        "items": [OrderItem("Violão Aurora Nylon Natural", 1)],
        "deadlines": return_deadlines(date(2026, 1, 10), date(2026, 1, 15), date(2026, 1, 20)),
    }
    return OrderStatus(**(fields | overrides))


def test_payment_label():
    assert payment_label("pix", None) == "PIX"
    assert payment_label("boleto", None) == "boleto bancário"
    assert payment_label("credit_card", 6) == "cartão de crédito em 6x"


def test_delivered_order():
    data = order_to_dict(make_order())

    assert data["status"] == "entregue"
    assert data["order_date"] == "10/01/2026"
    assert data["total"] == "R$ 499,90"
    assert data["items"] == ["1x Violão Aurora Nylon Natural"]
    assert data["tracking_code"] == "BRAA1111111BR"
    assert data["return_deadlines"][0] == {
        "type": "arrependimento",
        "until": "22/01/2026",
        "situation": "dentro do prazo (faltam 2 dias)",
    }


def test_order_not_yet_delivered_explains_when_deadlines_start():
    data = order_to_dict(
        make_order(status="confirmed", tracking_code=None, estimated_delivery=None, deadlines=[])
    )

    assert data["status"] == "confirmado (pagamento aprovado, em separação)"
    assert "tracking_code" not in data
    assert "return_deadlines" not in data
    assert "a partir do recebimento" in data["return_deadlines_note"]


def test_cancelled_order_shows_reason_without_deadlines():
    data = order_to_dict(
        make_order(status="cancelled", notes="Pedido cancelado pelo cliente", deadlines=[])
    )

    assert data["notes"] == "Pedido cancelado pelo cliente"
    assert "return_deadlines" not in data
    assert "return_deadlines_note" not in data


def test_does_not_expose_contact_data():
    assert not {"email", "phone", "customer_name"} & set(order_to_dict(make_order()))
