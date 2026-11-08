"""Return, exchange and warranty deadlines (policy manual, sections 4 and 8.1).

The data has no real receipt date; `estimated_delivery` is used as a proxy (ADR 0001, assumption 8).
"""

from dataclasses import dataclass
from datetime import date, timedelta

WITHDRAWAL_DAYS = 7  # 4.1: after receipt, online purchases
DEFECT_EXCHANGE_DAYS = 30  # 4.2: after purchase
PREFERENCE_EXCHANGE_DAYS = 7  # 4.3: start not stated; counted from receipt (ADR 0001)
LEGAL_WARRANTY_DAYS = 90  # 8.1: after receipt


@dataclass(frozen=True)
class Deadline:
    name: str
    until: date
    today: date

    @property
    def is_open(self) -> bool:
        return self.today <= self.until

    @property
    def days_left(self) -> int:
        return max((self.until - self.today).days, 0)


def return_deadlines(order_date: date, received_on: date, today: date) -> list[Deadline]:
    """Deadlines for a delivered order, in the order a customer usually asks about them."""
    return [
        Deadline("arrependimento", received_on + timedelta(days=WITHDRAWAL_DAYS), today),
        Deadline(
            "troca por preferência",
            received_on + timedelta(days=PREFERENCE_EXCHANGE_DAYS),
            today,
        ),
        Deadline("troca por defeito", order_date + timedelta(days=DEFECT_EXCHANGE_DAYS), today),
        Deadline("garantia legal", received_on + timedelta(days=LEGAL_WARRANTY_DAYS), today),
    ]
