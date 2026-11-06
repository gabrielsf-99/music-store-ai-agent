"""Price rules from the store policy manual (sections 3, 5.1 and 6.2)."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PIX_DISCOUNT_PERCENT = 5
MAX_INSTALLMENTS = 12

# (max installments in the tier, minimum installment value), section 3.1.
# Up to 3x the manual says "no minimum, except below R$ 50,00" (ADR 0001, assumption 3).
INSTALLMENT_TIERS = (
    (3, Decimal("50.00")),
    (6, Decimal("80.00")),
    (12, Decimal("100.00")),
)

METRO_FREE_SHIPPING_ABOVE = Decimal("500.00")
METRO_SHIPPING_FEE = Decimal("35.00")

_CENTS = Decimal("0.01")


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def apply_discount(price: Decimal, percent: int) -> Decimal:
    return to_cents(price * (100 - percent) / 100)


def minimum_installment_value(installments: int) -> Decimal:
    for tier_max, minimum in INSTALLMENT_TIERS:
        if installments <= tier_max:
            return minimum
    raise ValueError(f"installments must be between 1 and {MAX_INSTALLMENTS}")


def max_installments(total: Decimal) -> int:
    """Highest number of interest-free installments allowed for `total` (1x is always allowed)."""
    for installments in range(MAX_INSTALLMENTS, 1, -1):
        if total / installments >= minimum_installment_value(installments):
            return installments
    return 1


def installment_value(total: Decimal, installments: int) -> Decimal:
    return to_cents(total / installments)


def metro_shipping_fee(order_total: Decimal) -> Decimal:
    """Delivery fee in the Campo Grande metropolitan region (section 5.1)."""
    return Decimal("0.00") if order_total > METRO_FREE_SHIPPING_ABOVE else METRO_SHIPPING_FEE


@dataclass(frozen=True)
class Price:
    list_price: Decimal
    discount_percent: int | None
    promotion_name: str | None
    final_price: Decimal
    pix_price: Decimal
    max_installments: int
    installment_value: Decimal

    @property
    def has_promotion(self) -> bool:
        return self.discount_percent is not None

    @property
    def pix_discount_applies(self) -> bool:
        return not self.has_promotion


def price_product(
    list_price: Decimal, discount_percent: int | None = None, promotion_name: str | None = None
) -> Price:
    """Final price, PIX price and installments. Promotions do not stack with the PIX discount."""
    list_price = to_cents(list_price)
    if discount_percent is None:
        final_price = list_price
        pix_price = apply_discount(list_price, PIX_DISCOUNT_PERCENT)
    else:
        final_price = apply_discount(list_price, discount_percent)
        pix_price = final_price

    installments = max_installments(final_price)
    return Price(
        list_price=list_price,
        discount_percent=discount_percent,
        promotion_name=promotion_name if discount_percent is not None else None,
        final_price=final_price,
        pix_price=pix_price,
        max_installments=installments,
        installment_value=installment_value(final_price, installments),
    )


def format_brl(value: Decimal) -> str:
    """Decimal(2199.5) -> 'R$ 2.199,50'."""
    formatted = f"{to_cents(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"
