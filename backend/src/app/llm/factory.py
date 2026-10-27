"""LLM client factory.

The only place where AsyncAnthropic/AsyncOpenAI appear. The container hands
in ready settings: the main profile or the cheap one
(CheapLLMSettings.resolve(fallback)). For tests a hand-made SDK client can
be injected instead of the factory one.
"""

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from src.app.core.settings.llm import LLMSettings
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.claude_client import ClaudeClient
from src.app.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient

_OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"


def create_llm_client(settings: LLMSettings) -> LLMClient:
    """Собрать клиента выбранного провайдера; SDK-клиент не подключается."""
    if settings.provider == "anthropic":
        client = AsyncAnthropic(
            api_key=settings.api_key.get_secret_value() if settings.api_key else None,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )
        return ClaudeClient(client=client, settings=settings)

    api_key = settings.api_key.get_secret_value() if settings.api_key else None
    base_url = settings.base_url
    if settings.provider == "ollama":
        api_key = api_key or "ollama"
        base_url = base_url or _OLLAMA_DEFAULT_BASE_URL

    openai_client = AsyncOpenAI(
        api_key=api_key or "dummy-key",
        base_url=base_url,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    return OpenAICompatibleLLMClient(client=openai_client, settings=settings)
