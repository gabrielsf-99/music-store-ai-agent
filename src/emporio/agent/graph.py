import logging
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from psycopg_pool import ConnectionPool

from emporio.agent.guardrail import Classifier, build_guardrail_node, llm_classifier
from emporio.agent.tools import build_catalog_tools, build_order_tools, build_policy_tools
from emporio.config import Settings, get_settings
from emporio.llm import build_chat_model
from emporio.prompts.system import build_system_prompt
from emporio.rag.embeddings import embed_texts, warm_up
from emporio.tools.catalog import list_offered_categories

log = logging.getLogger(__name__)

TOOL_FAILURE_MESSAGE = (
    "Erro interno ao consultar o sistema. Peça desculpas ao cliente, diga que não foi possível "
    "consultar agora e oriente a tentar novamente mais tarde ou falar com a equipe pelo WhatsApp."
)


class AgentState(MessagesState):
    scope: str  # last guardrail decision: in_scope, accessory, off_topic or manipulation


def tool_failure_message(error: Exception) -> str:
    """Any tool error becomes a tool message, so a saved conversation is never left with an
    unanswered tool call (providers reject such histories on every following turn)."""
    log.exception("tool failed", exc_info=error)
    return TOOL_FAILURE_MESSAGE


def _route_after_guardrail(state: AgentState) -> str:
    return "agent" if state.get("scope") == "in_scope" else END


def build_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: Callable[[], str],
    checkpointer: BaseCheckpointSaver | None = None,
    classify: Classifier | None = None,
) -> CompiledStateGraph:
    """[guardrail ->] agent -> (tools -> agent)* -> end. The system prompt is rebuilt every turn.

    Without `classify`, the guardrail is skipped (used by tests of the agent loop alone).
    """
    llm_with_tools = llm.bind_tools(tools)

    def agent(state: AgentState) -> dict:
        messages = [SystemMessage(system_prompt()), *state["messages"]]
        return {"messages": [llm_with_tools.invoke(messages)]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=tool_failure_message))
    if classify is None:
        builder.add_edge(START, "agent")
    else:
        builder.add_node("guardrail", build_guardrail_node(classify))
        builder.add_edge(START, "guardrail")
        builder.add_conditional_edges("guardrail", _route_after_guardrail, ["agent", END])
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
        categories = list_offered_categories(conn)
    warm_up()

    def now() -> datetime:
        return datetime.now(timezone)

    return build_graph(
        llm=build_chat_model(settings, streaming=True),
        tools=[
            *build_catalog_tools(pool),
            *build_policy_tools(pool, embed_texts),
            *build_order_tools(pool, today=lambda: now().date()),
        ],
        system_prompt=lambda: build_system_prompt(now(), categories),
        checkpointer=checkpointer,
        classify=llm_classifier(build_chat_model(settings, reasoning_effort="low")),
    )
