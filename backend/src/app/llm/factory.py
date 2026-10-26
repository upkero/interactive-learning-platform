from openai import AsyncOpenAI

from src.app.core.settings.llm import LLMSettings
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient


def create_llm_client(settings: LLMSettings) -> LLMClient:
    api_key = settings.api_key.get_secret_value() if settings.api_key is not None else None
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=settings.base_url,
        timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    return OpenAICompatibleLLMClient(client=client, settings=settings)
