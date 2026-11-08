from fake_llm import scripted, tool_call
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from emporio.agent.graph import TOOL_FAILURE_MESSAGE, build_graph


@tool
def broken_lookup(query: str) -> str:
    """Always fails, like a tool whose database is unavailable."""
    raise RuntimeError("relation does not exist")


def test_tool_exception_becomes_tool_message_and_conversation_continues():
    llm = scripted(tool_call("broken_lookup", {"query": "x"}), AIMessage("Desculpe, tente depois."))
    graph = build_graph(llm, [broken_lookup], system_prompt=lambda: "sistema")

    result = graph.invoke({"messages": [HumanMessage("oi")]})

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].content == TOOL_FAILURE_MESSAGE
    assert result["messages"][-1].content == "Desculpe, tente depois."
