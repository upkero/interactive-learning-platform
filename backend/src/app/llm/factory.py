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
OPENROUTER_ANTHROPIC_BASE_URL = "https://openrouter.ai/api"


def create_anthropic_sdk_client(settings: LLMSettings) -> AsyncAnthropic:
    """Build the native Messages client, including OpenRouter's bearer authentication."""
    if settings.provider != "anthropic" or settings.api_key is None:
        raise ValueError("The Anthropic client requires an API key and the anthropic provider")
    secret = settings.api_key.get_secret_value()
    uses_openrouter = (settings.base_url or "").rstrip("/") == OPENROUTER_ANTHROPIC_BASE_URL
    return AsyncAnthropic(
        api_key="" if uses_openrouter else secret,
        auth_token=secret if uses_openrouter else None,
        base_url=settings.base_url,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )


def create_llm_client(settings: LLMSettings) -> LLMClient:
    """Build the provider client for the given settings profile."""
    if settings.provider == "anthropic":
        return ClaudeClient(client=create_anthropic_sdk_client(settings), settings=settings)

    api_key = settings.api_key.get_secret_value() if settings.api_key else None
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
