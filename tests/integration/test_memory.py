import pytest
from fake_llm import scripted
from langchain_core.messages import AIMessage, HumanMessage

from emporio.agent.graph import build_graph
from emporio.agent.memory import create_checkpointer
from emporio.db.connection import create_pool

pytestmark = pytest.mark.integration


def test_conversation_survives_rebuilding_the_agent(database_url, conn, test_schema):
    config = {"configurable": {"thread_id": "cliente-123"}}

    with create_pool(database_url, test_schema, max_size=2, autocommit=True) as memory_pool:
        first = build_graph(
            scripted(AIMessage("Olá! Como posso ajudar?")),
            [],
            system_prompt=lambda: "sistema",
            checkpointer=create_checkpointer(memory_pool),
        )
        first.invoke({"messages": [HumanMessage("oi")]}, config)

    # A new pool and graph, as after an application restart.
    with create_pool(database_url, test_schema, max_size=2, autocommit=True) as memory_pool:
        second = build_graph(
            scripted(AIMessage("Claro!")),
            [],
            system_prompt=lambda: "sistema",
            checkpointer=create_checkpointer(memory_pool),
        )
        result = second.invoke({"messages": [HumanMessage("e agora?")]}, config)

    assert [m.content for m in result["messages"]] == [
        "oi",
        "Olá! Como posso ajudar?",
        "e agora?",
        "Claro!",
    ]


def test_threads_are_isolated(database_url, conn, test_schema):
    with create_pool(database_url, test_schema, max_size=2, autocommit=True) as memory_pool:
        graph = build_graph(
            scripted(AIMessage("resposta A"), AIMessage("resposta B")),
            [],
            system_prompt=lambda: "sistema",
            checkpointer=create_checkpointer(memory_pool),
        )
        graph.invoke({"messages": [HumanMessage("A")]}, {"configurable": {"thread_id": "a"}})
        result = graph.invoke(
            {"messages": [HumanMessage("B")]}, {"configurable": {"thread_id": "b"}}
        )

    assert [m.content for m in result["messages"]] == ["B", "resposta B"]
