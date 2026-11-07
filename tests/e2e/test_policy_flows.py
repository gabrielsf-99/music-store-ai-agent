"""Agent conversations about store policies, using the synthetic manual from tests/conftest.py."""

import pytest

pytestmark = pytest.mark.e2e


def test_return_question_applies_withdrawal_policy(ask):
    turn = ask("Me arrependi de uma compra que recebi ontem, posso devolver?")

    assert "search_policies" in turn.tool_names
    assert "7 dias" in turn.answer


def test_defect_question_applies_exchange_policy(ask):
    turn = ask("Meu instrumento chegou com defeito, o que eu faço?")

    assert "search_policies" in turn.tool_names
    assert "30 dias" in turn.answer
