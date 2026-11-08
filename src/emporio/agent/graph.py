import logging
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

from emporio.agent.tools import build_catalog_tools, build_order_tools, build_policy_tools
from emporio.config import Settings, get_settings
from emporio.llm import build_chat_model
from emporio.prompts.system import build_system_prompt
from emporio.rag.embeddings import embed_texts, warm_up

log = logging.getLogger(__name__)

TOOL_FAILURE_MESSAGE = (
    "Erro interno ao consultar o sistema. Peça desculpas ao cliente, diga que não foi possível "
    "consultar agora e oriente a tentar novamente mais tarde ou falar com a equipe pelo WhatsApp."
)


def tool_failure_message(error: Exception) -> str:
    """Any tool error becomes a tool message, so a saved conversation is never left with an
    unanswered tool call (providers reject such histories on every following turn)."""
    log.exception("tool failed", exc_info=error)
    return TOOL_FAILURE_MESSAGE


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
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=tool_failure_message))
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
    warm_up()

    def now() -> datetime:
        return datetime.now(timezone)

    return build_graph(
        llm=build_chat_model(settings),
        tools=[
            *build_catalog_tools(pool),
            *build_policy_tools(pool, embed_texts),
            *build_order_tools(pool, today=lambda: now().date()),
        ],
        system_prompt=lambda: build_system_prompt(now(), categories),
        checkpointer=checkpointer,
    )
