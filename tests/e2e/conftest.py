import uuid
from dataclasses import dataclass

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from emporio.agent.graph import build_agent
from emporio.config import get_settings
from emporio.db.connection import create_pool


@dataclass
class Turn:
    answer: str
    tool_calls: list[dict]

    @property
    def tool_names(self) -> list[str]:
        return [call["name"] for call in self.tool_calls]


@pytest.fixture
def agent(database_url, loaded_conn, test_schema):
    settings = get_settings()
    if not (settings.openrouter_api_key and settings.llm_model):
        pytest.skip("OPENROUTER_API_KEY and LLM_MODEL are required for e2e tests")
    with create_pool(database_url, test_schema, max_size=2) as pool:
        yield build_agent(pool, settings, checkpointer=InMemorySaver())


@pytest.fixture
def ask(agent):
    """Send messages in one conversation; returns the answer and the tools called in that turn."""
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    def _ask(text: str) -> Turn:
        before = len(agent.get_state(config).values.get("messages", []))
        result = agent.invoke({"messages": [HumanMessage(text)]}, config)
        new_messages = result["messages"][before:]
        calls = [c for m in new_messages if isinstance(m, AIMessage) for c in m.tool_calls]
        return Turn(answer=result["messages"][-1].text, tool_calls=calls)

    return _ask
