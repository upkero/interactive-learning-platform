from openai import AsyncOpenAI

from src.app.core.settings.llm import LLMSettings
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient


def create_llm_client(settings: LLMSettings) -> LLMClient:
    api_key = settings.api_key.get_secret_value() if settings.api_key is not None else None
    base_url = settings.base_url

    if settings.provider == "ollama":
        api_key = api_key or "ollama"
        base_url = base_url or "http://localhost:11434/v1"
    elif settings.provider == "anthropic" and base_url is None:
        base_url = "https://api.anthropic.com/v1"

    client = AsyncOpenAI(
        api_key=api_key or "dummy-key",
        base_url=base_url,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    return OpenAICompatibleLLMClient(client=client, settings=settings)
