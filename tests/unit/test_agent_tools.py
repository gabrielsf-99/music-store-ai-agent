from decimal import Decimal

import pytest

from emporio.agent.tools import availability, offer_to_dict
from emporio.domain.pricing import price_product
from emporio.tools.catalog import ProductOffer


def make_offer(status="active", stock=5, price="2199", discount=None, promo=None):
    return ProductOffer(
        product_id=95,
        name="Takamine GD20 Dreadnought Natural",
        category="Violões",
        status=status,
        stock_quantity=stock,
        price=price_product(Decimal(price), discount, promo),
    )


@pytest.mark.parametrize(
    ("status", "stock", "label"),
    [
        ("active", 5, "disponível"),
        ("active", 0, "esgotado no momento"),
        ("discontinued", 0, "descontinuado (não faz mais parte do catálogo)"),
        ("coming_soon", 2, "em breve (ainda não disponível para venda)"),
    ],
)
def test_availability(status, stock, label):
    assert availability(make_offer(status=status, stock=stock)) == label


def test_offer_without_promotion():
    data = offer_to_dict(make_offer())

    assert data["price"] == "R$ 2.199,00"
    assert data["pix_price"] == "R$ 2.089,05"
    assert data["pix_discount"] == "5%"
    assert data["installments"] == "até 12x de R$ 183,25 sem juros"
    assert "promotion" not in data


def test_offer_with_promotion_shows_original_price_and_no_pix_discount():
    data = offer_to_dict(make_offer(price="359", discount=10, promo="Oferta Especial"))

    assert data["price"] == "R$ 323,10"
    assert data["pix_price"] == "R$ 323,10"
    assert data["pix_discount"] == "não se aplica (produto em promoção)"
    assert data["promotion"] == {
        "name": "Oferta Especial",
        "discount": "10%",
        "original_price": "R$ 359,00",
    }


def test_offer_below_minimum_installment_is_cash_only():
    assert offer_to_dict(make_offer(price="99.9"))["installments"] == "somente à vista"
