from datetime import date

import pytest

from emporio.domain.returns import return_deadlines

ORDER_DATE = date(2026, 1, 10)
RECEIVED = date(2026, 1, 15)


def deadlines_on(today: date) -> dict:
    return {d.name: d for d in return_deadlines(ORDER_DATE, RECEIVED, today)}


def test_deadline_dates():
    deadlines = deadlines_on(RECEIVED)

    assert deadlines["arrependimento"].until == date(2026, 1, 22)  # receipt + 7
    assert deadlines["troca por preferência"].until == date(2026, 1, 22)  # receipt + 7
    assert deadlines["troca por defeito"].until == date(2026, 2, 9)  # purchase + 30
    assert deadlines["garantia legal"].until == date(2026, 4, 15)  # receipt + 90


@pytest.mark.parametrize(
    ("today", "is_open", "days_left"),
    [
        (date(2026, 1, 21), True, 1),
        (date(2026, 1, 22), True, 0),  # last day still counts
        (date(2026, 1, 23), False, 0),
    ],
)
def test_withdrawal_window_boundaries(today, is_open, days_left):
    withdrawal = deadlines_on(today)["arrependimento"]

    assert withdrawal.is_open is is_open
    assert withdrawal.days_left == days_left


@pytest.mark.parametrize(
    ("today", "is_open"), [(date(2026, 2, 9), True), (date(2026, 2, 10), False)]
)
def test_defect_exchange_counts_from_purchase_date(today, is_open):
    assert deadlines_on(today)["troca por defeito"].is_open is is_open
