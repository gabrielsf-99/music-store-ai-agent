"""Fixed store information and opening hours (policy manual, sections 1.2 and 2)."""

from datetime import datetime, time, timedelta

STORE_NAME = "Empório da Música"
ADDRESS = "Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333"
PHONE_WHATSAPP = "(67) 3341-4444"
EMAIL = "contato@emporiodamusica.com.br"

# datetime.weekday() -> (opens, closes). Sunday (6) is closed. Holidays are not modeled.
OPENING_HOURS = {
    0: (time(9), time(18)),
    1: (time(9), time(18)),
    2: (time(9), time(18)),
    3: (time(9), time(18)),
    4: (time(9), time(18)),
    5: (time(9), time(13)),
}

WEEKDAYS_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def is_open(now: datetime) -> bool:
    hours = OPENING_HOURS.get(now.weekday())
    return hours is not None and hours[0] <= now.time() < hours[1]


def next_opening(now: datetime) -> datetime:
    """Next moment the store opens, strictly after `now`."""
    for days_ahead in range(8):
        day = now + timedelta(days=days_ahead)
        hours = OPENING_HOURS.get(day.weekday())
        if hours is None:
            continue
        opening = day.replace(hour=hours[0].hour, minute=0, second=0, microsecond=0)
        if opening > now:
            return opening
    raise AssertionError("OPENING_HOURS has no open day")
