"""Agent conversations about the catalog, using the synthetic fixture dataset.

Assertions check tools called and key facts, never the exact wording.
"""

import pytest

pytestmark = pytest.mark.e2e


def test_price_question_uses_catalog_and_reports_promotion(ask):
    turn = ask("Quanto custa o violão Aurora?")

    assert {"get_product_details", "search_products"} & set(turn.tool_names)
    assert "449,91" in turn.answer  # promotional price
    assert "499,90" in turn.answer  # original price shown alongside the promotion
    assert "10%" in turn.answer


def test_catalog_question_lists_only_available_products(ask):
    turn = ask("Quais violões vocês têm até R$ 1000?")

    assert "search_products" in turn.tool_names
    assert "Aurora" in turn.answer
    assert "Pampa" not in turn.answer  # discontinued
