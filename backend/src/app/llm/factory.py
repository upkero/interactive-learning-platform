"""LLM client factory.

The only place where AsyncAnthropic/AsyncOpenAI are constructed. The
container hands in ready settings: the main profile or the cheap one
(CheapLLMSettings.resolve(fallback)). Tests do not use the factory — they
build their own SDK clients over a mocked HTTP transport and pass them to
the client classes directly.
"""

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from src.app.core.settings.llm import LLMSettings
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.claude_client import ClaudeClient
from src.app.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient

_OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"


def create_llm_client(settings: LLMSettings) -> LLMClient:
    """Build the provider client for the given settings profile."""
    # The settings validator requires api_key for anthropic and
    # openai_compatible; ollama may omit it (handled below).
    api_key = settings.api_key.get_secret_value() if settings.api_key else None

    if settings.provider == "anthropic":
        client = AsyncAnthropic(
            api_key=api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )
        return ClaudeClient(client=client, settings=settings)

    base_url = settings.base_url
    if settings.provider == "ollama":
        # AsyncOpenAI refuses to construct without a key; ollama ignores it.
        api_key = api_key or "ollama"
        base_url = base_url or _OLLAMA_DEFAULT_BASE_URL

    openai_client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    return OpenAICompatibleLLMClient(client=openai_client, settings=settings)
