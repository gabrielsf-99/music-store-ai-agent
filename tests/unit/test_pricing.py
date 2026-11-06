from decimal import Decimal

import pytest

from emporio.domain.pricing import (
    format_brl,
    installment_value,
    max_installments,
    metro_shipping_fee,
    minimum_installment_value,
    price_product,
)


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        ("99.90", 1),  # 2x would be R$ 49,95, below the R$ 50 minimum
        ("100.00", 2),
        ("160.00", 3),  # 4x would be R$ 40, below the R$ 80 minimum of the 4-6x tier
        ("599.00", 6),  # 7x would be R$ 85,57, below the R$ 100 minimum of the 7-12x tier
        ("1000.00", 10),  # 12x would be R$ 83,33: not allowed
        ("1200.00", 12),
        ("11499.00", 12),
    ],
)
def test_max_installments(total, expected):
    assert max_installments(Decimal(total)) == expected


@pytest.mark.parametrize(
    ("installments", "minimum"), [(1, "50"), (3, "50"), (4, "80"), (12, "100")]
)
def test_minimum_installment_value_tiers(installments, minimum):
    assert minimum_installment_value(installments) == Decimal(minimum)


def test_minimum_installment_value_rejects_more_than_12():
    with pytest.raises(ValueError):
        minimum_installment_value(13)


def test_installment_value_rounds_to_cents():
    assert installment_value(Decimal("599.00"), 6) == Decimal("99.83")


def test_price_without_promotion_gets_pix_discount():
    price = price_product(Decimal("2199"))

    assert price.final_price == Decimal("2199.00")
    assert price.pix_price == Decimal("2089.05")
    assert price.pix_discount_applies
    assert price.max_installments == 12
    assert price.installment_value == Decimal("183.25")


def test_promotion_does_not_stack_with_pix():
    price = price_product(Decimal("359"), 10, "Oferta Especial")

    assert price.list_price == Decimal("359.00")
    assert price.final_price == Decimal("323.10")
    assert price.pix_price == price.final_price
    assert not price.pix_discount_applies
    assert price.promotion_name == "Oferta Especial"


def test_installments_use_the_promotional_price():
    # List price R$ 1.200 allows 12x of R$ 100; with 10% off (R$ 1.080) 12x would be R$ 90.
    assert price_product(Decimal("1200")).max_installments == 12

    price = price_product(Decimal("1200"), 10, "Desconto")

    assert price.final_price == Decimal("1080.00")
    assert price.max_installments == 10
    assert price.installment_value == Decimal("108.00")


@pytest.mark.parametrize(
    ("total", "fee"), [("499.90", "35.00"), ("500.00", "35.00"), ("500.01", "0.00")]
)
def test_metro_shipping_fee(total, fee):
    assert metro_shipping_fee(Decimal(total)) == Decimal(fee)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2199", "R$ 2.199,00"),
        ("2089.05", "R$ 2.089,05"),
        ("49.9", "R$ 49,90"),
        ("19567", "R$ 19.567,00"),
    ],
)
def test_format_brl(value, expected):
    assert format_brl(Decimal(value)) == expected
