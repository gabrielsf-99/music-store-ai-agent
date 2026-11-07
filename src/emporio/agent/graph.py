from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from psycopg_pool import ConnectionPool

from emporio.agent.tools import build_catalog_tools
from emporio.config import Settings, get_settings
from emporio.llm import build_chat_model
from emporio.prompts.system import build_system_prompt


def build_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: Callable[[], str],
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """ReAct loop: agent -> (tools -> agent)* -> end. The system prompt is rebuilt every turn."""
    llm_with_tools = llm.bind_tools(tools)

    def agent(state: MessagesState) -> dict:
        messages = [SystemMessage(system_prompt()), *state["messages"]]
        return {"messages": [llm_with_tools.invoke(messages)]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)


def build_agent(
    pool: ConnectionPool,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    settings = settings or get_settings()
    timezone = ZoneInfo(settings.timezone)
    with pool.connection() as conn:
        categories = [row[0] for row in conn.execute("SELECT name FROM categories ORDER BY name")]

    return build_graph(
        llm=build_chat_model(settings),
        tools=build_catalog_tools(pool),
        system_prompt=lambda: build_system_prompt(datetime.now(timezone), categories),
        checkpointer=checkpointer,
    )
