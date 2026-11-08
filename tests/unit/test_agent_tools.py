from decimal import Decimal

import pytest

from emporio.agent.tools import (
    MAX_PRODUCTS_PER_RESULT,
    availability,
    offer_to_dict,
    offers_result,
    search_result,
)
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


def test_offers_result_reports_products_left_out():
    offers = [make_offer() for _ in range(MAX_PRODUCTS_PER_RESULT + 2)]

    result = offers_result(offers)

    assert result["total_found"] == MAX_PRODUCTS_PER_RESULT + 2
    assert result["shown"] == MAX_PRODUCTS_PER_RESULT
    assert len(result["products"]) == MAX_PRODUCTS_PER_RESULT
    assert "Há mais 2 produtos" in result["note"]


def test_offers_result_without_truncation_has_no_note():
    result = offers_result([make_offer()])

    assert result["total_found"] == result["shown"] == 1
    assert "note" not in result


def test_search_by_name_reports_unavailable_matches():
    offers = [make_offer(), make_offer(stock=0)]

    result = search_result(offers, only_available=True, query="GD20")

    assert result["total_found"] == 1
    assert result["unavailable_matches"] == [
        {"name": "Takamine GD20 Dreadnought Natural", "availability": "esgotado no momento"}
    ]
    assert "não diga que o produto não existe" in result["unavailable_note"]


def test_search_without_query_does_not_report_unavailable():
    result = search_result([make_offer(stock=0)], only_available=True, query=None)

    assert result["total_found"] == 0
    assert "unavailable_matches" not in result


def test_search_including_unavailable_lists_them_as_products():
    result = search_result([make_offer(stock=0)], only_available=False, query="GD20")

    assert result["total_found"] == 1
    assert "unavailable_matches" not in result
