"""Scripted chat model for testing graph wiring without calling a real LLM."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class ScriptedChatModel(GenericFakeChatModel):
    """Returns the given messages in order; `bind_tools` is a no-op.

    Streaming is disabled: the fake model cannot stream a tool-call message with no text.
    """

    disable_streaming: bool = True

    def bind_tools(self, tools, **kwargs):
        return self


def scripted(*messages: AIMessage) -> ScriptedChatModel:
    return ScriptedChatModel(messages=iter(messages))


def tool_call(name: str, args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])
