"""Web chat (Chainlit): uv run chainlit run app.py"""

import json
import logging

import chainlit as cl

from emporio.ui.events import GuardrailReply, Token, ToolEnd, ToolStart, in_thread, turn_events
from emporio.ui.runtime import get_graph

log = logging.getLogger(__name__)

TOOL_LABELS = {
    "search_products": "Buscando no catálogo",
    "get_product_details": "Consultando o produto",
    "list_active_promotions": "Consultando promoções",
    "search_policies": "Consultando as políticas da loja",
    "get_order_status": "Consultando o pedido",
}

ERROR_MESSAGE = (
    "Desculpe, tive um problema para responder agora. Tente de novo em instantes ou fale com "
    "a equipe pelo WhatsApp (67) 3341-4444."
)


@cl.data_layer
def no_chainlit_data_layer() -> None:
    """Chainlit would enable its own persistence because DATABASE_URL is set (our database).
    Conversations are already stored by LangGraph's PostgresSaver, so it stays off."""
    return None


@cl.set_starters
async def starters() -> list[cl.Starter]:
    return [
        cl.Starter(label="Violões até R$ 1.000", message="Quais violões vocês têm até R$ 1000?"),
        cl.Starter(label="Promoções", message="Tem alguma promoção rolando?"),
        cl.Starter(label="Trocas e devoluções", message="Me arrependi da compra, posso devolver?"),
        cl.Starter(label="Meu pedido", message="Quero saber do meu pedido"),
    ]


@cl.on_chat_start
async def start() -> None:
    # One LangGraph conversation per browser session (each tab is a new session).
    cl.user_session.set("thread_id", f"web-{cl.context.session.id}")


def _pretty(text: str) -> str:
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return text


@cl.on_message
async def on_message(message: cl.Message) -> None:
    graph = get_graph()
    config = {"configurable": {"thread_id": cl.user_session.get("thread_id")}}
    answer = cl.Message(content="")
    steps: dict[str, cl.Step] = {}

    try:
        events = in_thread(lambda: turn_events(graph, message.content, config))
        async for event in events:
            match event:
                case Token(text):
                    await answer.stream_token(text)
                case ToolStart(call_id, name, args):
                    step = cl.Step(name=TOOL_LABELS.get(name, name), type="tool")
                    step.input = json.dumps(args, ensure_ascii=False, indent=2)
                    step.language = "json"
                    await step.send()
                    steps[call_id] = step
                case ToolEnd(call_id, _, output):
                    if step := steps.pop(call_id, None):
                        step.output = _pretty(output)
                        await step.update()
                case GuardrailReply(_, text):
                    answer.content = text
    except Exception:
        log.exception("failed to answer")
        answer.content = ERROR_MESSAGE

    await answer.send()
