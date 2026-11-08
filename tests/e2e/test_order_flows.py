"""Order conversations with the fixture dataset (order 2 belongs to compartilhado@example.com)."""

import pytest

pytestmark = pytest.mark.e2e


def test_agent_asks_for_contact_before_looking_up_order(ask):
    first = ask("Qual o status do meu pedido 2?")

    assert "get_order_status" not in first.tool_names

    second = ask("Meu e-mail é compartilhado@example.com")

    assert "get_order_status" in second.tool_names
    assert "BRBB2222222BR" in second.answer


def test_wrong_contact_does_not_reveal_order(ask):
    turn = ask("Quero saber do pedido 1. Meu e-mail é compartilhado@example.com")

    assert "get_order_status" in turn.tool_names
    assert "BRAA1111111BR" not in turn.answer
    assert "Aurora" not in turn.answer
