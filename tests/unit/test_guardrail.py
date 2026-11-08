import pytest
from fake_llm import scripted, tool_call
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from emporio.agent.graph import build_graph
from emporio.agent.guardrail import (
    CONTEXT_MESSAGES,
    ScopeDecision,
    build_guardrail_node,
    build_transcript,
)


def fixed(category: str, reply: str = ""):
    return lambda messages: ScopeDecision(category=category, reply=reply)


def failing(messages):
    raise RuntimeError("provider unavailable")


def test_transcript_has_context_and_last_message_without_tool_traffic():
    messages = [
        HumanMessage("quero saber do pedido 1"),
        tool_call("get_order_status", {"order_id": 1, "email_or_phone": "x"}),
        ToolMessage("{...}", tool_call_id="call-1"),
        AIMessage("Me passa o e-mail da compra?"),
        HumanMessage("ana@example.com"),
    ]

    transcript = build_transcript(messages)

    assert transcript == (
        "Conversa recente:\n"
        "Cliente: quero saber do pedido 1\n"
        "Assistente: Me passa o e-mail da compra?\n\n"
        "Última mensagem do cliente:\n"
        "Cliente: ana@example.com"
    )


def test_transcript_keeps_only_recent_messages():
    messages = [HumanMessage(f"mensagem {i}") for i in range(CONTEXT_MESSAGES + 4)]

    transcript = build_transcript(messages)

    assert "mensagem 3\n" not in transcript
    assert f"mensagem {CONTEXT_MESSAGES + 3}" in transcript


def test_first_message_has_no_history():
    assert "(início da conversa)" in build_transcript([HumanMessage("oi")])


def test_in_scope_passes_without_reply():
    result = build_guardrail_node(fixed("in_scope"))({"messages": [HumanMessage("oi")]})

    assert result == {"scope": "in_scope"}


@pytest.mark.parametrize("category", ["accessory", "off_topic", "manipulation"])
def test_out_of_scope_answers_directly(category):
    node = build_guardrail_node(fixed(category, " Trabalhamos só com instrumentos. "))

    result = node({"messages": [HumanMessage("vocês vendem palhetas?")]})

    assert result["scope"] == category
    assert result["messages"][0].content == "Trabalhamos só com instrumentos."


def test_blocked_decision_without_reply_lets_message_through():
    result = build_guardrail_node(fixed("off_topic", ""))({"messages": [HumanMessage("x")]})

    assert result == {"scope": "in_scope"}


def test_classifier_failure_lets_message_through():
    result = build_guardrail_node(failing)({"messages": [HumanMessage("oi")]})

    assert result == {"scope": "in_scope"}


def test_graph_skips_agent_when_blocked():
    # No scripted messages: calling the agent's LLM would raise.
    graph = build_graph(
        scripted(), [], system_prompt=lambda: "sistema", classify=fixed("off_topic", "Não sei.")
    )

    result = graph.invoke({"messages": [HumanMessage("quem ganhou o jogo?")]})

    assert result["scope"] == "off_topic"
    assert [m.content for m in result["messages"]] == ["quem ganhou o jogo?", "Não sei."]


def test_graph_calls_agent_when_in_scope():
    graph = build_graph(
        scripted(AIMessage("Temos sim!")),
        [],
        system_prompt=lambda: "sistema",
        classify=fixed("in_scope"),
    )

    result = graph.invoke({"messages": [HumanMessage("tem violão?")]})

    assert result["messages"][-1].content == "Temos sim!"
