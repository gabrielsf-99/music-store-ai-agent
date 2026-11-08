"""Scope guardrail: one structured LLM call before the agent.

Clearly out-of-scope messages are answered here, without tools. Anything else, including a
guardrail failure, goes to the agent (fail open: blocking a real customer is the worse error).
"""

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "guardrail.md").read_text("utf-8")
CONTEXT_MESSAGES = 6  # human/assistant text messages shown to the classifier

Scope = Literal["in_scope", "accessory", "off_topic", "manipulation"]


class ScopeDecision(BaseModel):
    category: Scope = Field(description="Categoria da última mensagem do cliente.")
    reply: str = Field(
        default="", description="Resposta ao cliente se category != in_scope; senão, vazio."
    )


Classifier = Callable[[list[BaseMessage]], ScopeDecision]


def build_transcript(messages: Sequence[BaseMessage]) -> str:
    """Recent conversation as plain text. Tool calls and results are left out on purpose:
    sliced tool messages would be rejected by the provider and add nothing to the decision."""
    lines = []
    for message in messages:
        if isinstance(message, HumanMessage):
            lines.append(f"Cliente: {message.text}")
        elif isinstance(message, AIMessage) and message.text:
            lines.append(f"Assistente: {message.text}")
    recent = lines[-CONTEXT_MESSAGES:]
    if not recent:
        return ""
    *history, last = recent
    context = "\n".join(history) if history else "(início da conversa)"
    return f"Conversa recente:\n{context}\n\nÚltima mensagem do cliente:\n{last}"


def llm_classifier(llm: BaseChatModel) -> Classifier:
    structured = llm.with_structured_output(ScopeDecision)
    return structured.invoke


def build_guardrail_node(classify: Classifier) -> Callable[[dict], dict]:
    def guardrail(state: dict) -> dict:
        transcript = build_transcript(state["messages"])
        try:
            decision = classify([SystemMessage(PROMPT), HumanMessage(transcript)])
        except Exception:
            log.exception("guardrail failed; letting the message through")
            return {"scope": "in_scope"}

        if decision.category == "in_scope" or not decision.reply.strip():
            return {"scope": "in_scope"}
        return {"scope": decision.category, "messages": [AIMessage(decision.reply.strip())]}

    return guardrail
