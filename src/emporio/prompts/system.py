from datetime import datetime
from pathlib import Path

from emporio.domain import store

TEMPLATE = (Path(__file__).parent / "system.md").read_text(encoding="utf-8")


def describe_now(now: datetime) -> str:
    stamp = f"{store.WEEKDAYS_PT[now.weekday()]}, {now:%d/%m/%Y %H:%M}"
    if store.is_open(now):
        return f"{stamp}. A loja está aberta."
    opening = store.next_opening(now)
    weekday = store.WEEKDAYS_PT[opening.weekday()]
    return (
        f"{stamp}. A loja está fechada; reabre {weekday}, {opening:%d/%m} às {opening:%H:%M}. "
        "Se o cliente precisar da equipe, informe esse horário de retorno."
    )


def build_system_prompt(now: datetime, categories: list[str]) -> str:
    return TEMPLATE.format(
        store_name=store.STORE_NAME,
        address=store.ADDRESS,
        phone=store.PHONE_WHATSAPP,
        email=store.EMAIL,
        now_line=describe_now(now),
        categories=", ".join(categories),
    )
