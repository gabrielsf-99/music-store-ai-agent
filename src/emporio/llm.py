from langchain_openai import ChatOpenAI

from emporio.config import Settings, get_settings

LLM_TIMEOUT_SECONDS = 60


def build_chat_model(
    settings: Settings | None = None,
    reasoning_effort: str | None = None,
    streaming: bool = False,
) -> ChatOpenAI:
    """OpenRouter chat model. No temperature is sent: reasoning models reject it.

    `reasoning_effort` ("low", "medium", "high") trades answer depth for latency; used for the
    guardrail, a simple classification. `streaming` makes the answer arrive token by token.
    """
    settings = settings or get_settings()
    if not settings.llm_model or not settings.openrouter_api_key:
        raise RuntimeError("Defina OPENROUTER_API_KEY e LLM_MODEL no .env")
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=2,
        reasoning_effort=reasoning_effort,
        streaming=streaming,
    )
