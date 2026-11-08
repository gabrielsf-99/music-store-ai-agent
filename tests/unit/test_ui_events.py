import asyncio

import pytest
from fake_llm import scripted, tool_call
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from emporio.agent.graph import build_graph
from emporio.agent.guardrail import ScopeDecision
from emporio.ui.events import GuardrailReply, Token, ToolEnd, ToolStart, in_thread, turn_events

CONFIG = {"configurable": {"thread_id": "t"}}


@tool
def get_product_details(product: str) -> dict:
    """Fake product lookup."""
    return {"name": product, "price": "R$ 2.199,00"}


def classify_as(category: str, reply: str = ""):
    return lambda messages: ScopeDecision(category=category, reply=reply)


def test_tool_call_then_streamed_answer():
    graph = build_graph(
        scripted(
            tool_call("get_product_details", {"product": "Takamine GD20"}, call_id="c1"),
            AIMessage("Custa R$ 2.199,00 no cartão."),
        ),
        [get_product_details],
        system_prompt=lambda: "sistema",
        classify=classify_as("in_scope"),
    )

    events = list(turn_events(graph, "Quanto custa o Takamine GD20?", CONFIG))

    assert events[0] == ToolStart("c1", "get_product_details", {"product": "Takamine GD20"})
    assert isinstance(events[1], ToolEnd)
    assert events[1].call_id == "c1"
    assert "R$ 2.199,00" in events[1].output
    tokens = [e.text for e in events[2:]]
    assert all(isinstance(e, Token) for e in events[2:])
    assert "".join(tokens) == "Custa R$ 2.199,00 no cartão."


def test_blocked_message_yields_only_the_guardrail_reply():
    graph = build_graph(
        scripted(),
        [],
        system_prompt=lambda: "sistema",
        classify=classify_as("accessory", "Só vendemos instrumentos."),
    )

    events = list(turn_events(graph, "Vocês vendem palhetas?", CONFIG))

    assert events == [GuardrailReply("accessory", "Só vendemos instrumentos.")]


async def _collect(make_iterator):
    return [item async for item in in_thread(make_iterator)]


def test_in_thread_yields_items_in_order():
    assert asyncio.run(_collect(lambda: iter([1, 2, 3]))) == [1, 2, 3]


def test_in_thread_propagates_errors():
    def failing():
        yield 1
        raise RuntimeError("database down")

    with pytest.raises(RuntimeError, match="database down"):
        asyncio.run(_collect(failing))
