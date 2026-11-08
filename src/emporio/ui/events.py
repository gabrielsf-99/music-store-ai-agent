"""Turn a LangGraph run into simple UI events, independent of the web framework.

The graph is synchronous (PostgresSaver has no async API); `in_thread` runs it in a worker
thread and hands the events to async code (Chainlit) through a queue.
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph


@dataclass(frozen=True)
class Token:
    text: str


@dataclass(frozen=True)
class ToolStart:
    call_id: str
    name: str
    args: dict


@dataclass(frozen=True)
class ToolEnd:
    call_id: str
    name: str
    output: str


@dataclass(frozen=True)
class GuardrailReply:
    scope: str
    text: str


Event = Token | ToolStart | ToolEnd | GuardrailReply


def turn_events(graph: CompiledStateGraph, text: str, config: dict) -> Iterator[Event]:
    """Answer tokens as they are generated, plus tool calls and guardrail replies."""
    stream = graph.stream(
        {"messages": [HumanMessage(text)]}, config, stream_mode=["messages", "updates"]
    )
    for mode, payload in stream:
        if mode == "messages":
            chunk, metadata = payload
            # Only the agent's answer goes to the UI. Streaming models emit AIMessageChunk pieces;
            # non-streaming ones emit the whole AIMessage once (AIMessageChunk is a subclass).
            is_answer = metadata.get("langgraph_node") == "agent"
            if is_answer and isinstance(chunk, AIMessage) and chunk.text:
                yield Token(chunk.text)
            continue

        for node, update in payload.items():
            if not update:
                continue
            if node == "agent":
                for message in update["messages"]:
                    for call in message.tool_calls:
                        yield ToolStart(call["id"], call["name"], call["args"])
            elif node == "tools":
                for message in update["messages"]:
                    yield ToolEnd(message.tool_call_id, message.name, message.text)
            elif node == "guardrail" and update.get("scope") != "in_scope":
                yield GuardrailReply(update["scope"], update["messages"][0].text)


_DONE = object()


async def in_thread[T](make_iterator: Callable[[], Iterator[T]]) -> AsyncIterator[T]:
    """Consume a blocking iterator in a worker thread, yielding its items asynchronously."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def worker() -> None:
        try:
            for item in make_iterator():
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except BaseException as error:  # re-raised in the async consumer
            loop.call_soon_threadsafe(queue.put_nowait, error)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    worker_done = loop.run_in_executor(None, worker)
    while (item := await queue.get()) is not _DONE:
        if isinstance(item, BaseException):
            raise item
        yield item
    await worker_done
