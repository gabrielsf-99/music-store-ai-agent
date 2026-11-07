from datetime import datetime

import pytest

from emporio.domain.store import is_open, next_opening

# 2026-11-02 is a Monday.
MONDAY = 2
SATURDAY = 7
SUNDAY = 8


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (at(MONDAY, 8, 59), False),
        (at(MONDAY, 9, 0), True),
        (at(MONDAY, 17, 59), True),
        (at(MONDAY, 18, 0), False),
        (at(SATURDAY, 12, 59), True),
        (at(SATURDAY, 13, 0), False),
        (at(SUNDAY, 10, 0), False),
    ],
)
def test_is_open(moment, expected):
    assert is_open(moment) is expected


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (at(MONDAY, 7, 30), at(MONDAY, 9)),
        (at(MONDAY, 10, 0), at(MONDAY + 1, 9)),
        (at(SATURDAY, 14, 0), at(MONDAY + 7, 9)),
        (at(SUNDAY, 10, 0), at(MONDAY + 7, 9)),
    ],
)
def test_next_opening(moment, expected):
    assert next_opening(moment) == expected
