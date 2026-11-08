from pathlib import Path

import pytest
import yaml

from evals.scoring import (
    TurnResult,
    normalize,
    percentile,
    resolve_placeholders,
    score_turn,
    summarize,
)

DATASET = Path(__file__).parents[2] / "evals" / "dataset.yaml"
TOOLS = {
    "search_products",
    "get_product_details",
    "list_active_promotions",
    "search_policies",
    "get_order_status",
}
SCOPES = {"in_scope", "accessory", "off_topic", "manipulation"}


def test_normalize_ignores_case_accents_and_nbsp():
    assert normalize("Está  ESGOTADO agora") == "esta esgotado agora"


def test_resolve_placeholders():
    def lookup(kind, order_id):
        return f"<{kind}-{order_id}>"

    text = "Pedido 8, e-mail {order_email:8}, tel {order_phone:3}"
    assert resolve_placeholders(text, lookup) == "Pedido 8, e-mail <email-8>, tel <phone-3>"


def test_turn_ok_with_any_expected_tool_and_facts():
    expect = {"tools": ["get_product_details", "search_products"], "facts": ["2.199,00"]}

    result = score_turn(expect, "Custa R$ 2.199,00", ["search_products"], "in_scope")

    assert result.ok and result.problems == []


def test_wrong_tool_fails_routing():
    result = score_turn({"tools": ["search_policies"]}, "x", ["search_products"], "in_scope")

    assert not result.routing_ok
    assert "esperado uma de: search_policies" in result.problems[0]


def test_empty_tools_means_no_tool_allowed():
    result = score_turn({"tools": []}, "x", ["search_products"], "in_scope")

    assert not result.routing_ok


def test_scope_defaults_to_in_scope_and_accepts_a_list():
    assert not score_turn({}, "x", [], "accessory").routing_ok
    expect = {"scope": ["manipulation", "off_topic"]}
    assert score_turn(expect, "x", [], "off_topic").routing_ok


def test_facts_any_and_forbid():
    expect = {"facts_any": ["esgotado", "sem estoque"], "forbid": ["417,24"]}

    assert score_turn(expect, "Está sem estoque", [], "in_scope").facts_ok
    result = score_turn(expect, "No PIX fica 417,24", [], "in_scope")
    assert not result.facts_ok
    assert any("faltou um de" in p for p in result.problems)
    assert any("não deveria conter: 417,24" in p for p in result.problems)


def test_turn_without_fact_expectations_is_not_counted_in_facts():
    result = score_turn({"tools": []}, "Olá!", [], "in_scope")

    assert result.facts_ok is None and result.ok


def test_summarize():
    ok = TurnResult(routing_ok=True, facts_ok=True)
    no_facts = TurnResult(routing_ok=True, facts_ok=None)
    wrong = TurnResult(routing_ok=False, facts_ok=False)

    s = summarize([[ok], [no_facts, ok], [wrong]], [1.0, 2.0, 3.0, 10.0], cost_usd=0.5)

    assert (s.cases, s.cases_passed) == (3, 2)
    assert s.routing_accuracy == pytest.approx(3 / 4)
    assert s.facts_accuracy == pytest.approx(2 / 3)
    assert s.latency_p50 == 2.5
    assert s.latency_p95 == 10.0


def test_percentile_empty():
    assert percentile([], 95) == 0.0


def test_dataset_is_well_formed():
    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))

    assert 15 <= len(cases) <= 25
    assert len({c["id"] for c in cases}) == len(cases)
    allowed_keys = {"user", "tools", "scope", "facts", "facts_any", "forbid"}
    for case in cases:
        assert case["category"] and case["turns"], case["id"]
        for turn in case["turns"]:
            assert set(turn) <= allowed_keys, case["id"]
            assert set(turn.get("tools", [])) <= TOOLS, case["id"]
            scopes = turn.get("scope", "in_scope")
            assert set([scopes] if isinstance(scopes, str) else scopes) <= SCOPES, case["id"]
