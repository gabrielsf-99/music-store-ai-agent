from datetime import datetime

from emporio.prompts.system import build_system_prompt, describe_now


def test_describe_now_when_open():
    assert describe_now(datetime(2026, 11, 5, 15, 30)) == (
        "quinta-feira, 05/11/2026 15:30. A loja está aberta."
    )


def test_describe_now_when_closed_tells_next_opening():
    line = describe_now(datetime(2026, 11, 7, 20, 0))  # Saturday night

    assert line.startswith("sábado, 07/11/2026 20:00. A loja está fechada")
    assert "reabre segunda-feira, 09/11 às 09:00" in line


def test_system_prompt_includes_store_data_time_and_categories():
    prompt = build_system_prompt(datetime(2026, 11, 5, 15, 30), ["Ukuleles", "Violões"])

    assert "Rua 14 de Maio, 3200" in prompt
    assert "(67) 3341-4444" in prompt
    assert "quinta-feira, 05/11/2026 15:30" in prompt
    assert "Categorias com produtos no catálogo: Ukuleles, Violões." in prompt
    assert "{" not in prompt  # every placeholder was filled
