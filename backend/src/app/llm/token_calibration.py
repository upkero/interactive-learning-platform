"""Anthropic token-counting adapter for the explicitly invoked calibration tool."""

from anthropic.types import MessageParam

from src.app.core.settings.llm import LLMSettings
from src.app.llm.factory import OPENROUTER_ANTHROPIC_BASE_URL, create_anthropic_sdk_client


async def count_provider_tokens(
    settings: LLMSettings, texts: list[str], *, openrouter_usage: bool = False
) -> list[int]:
    """Call the provider; callers must authorize external requests beforehand."""
    if openrouter_usage and (
        (settings.base_url or "").rstrip("/") != OPENROUTER_ANTHROPIC_BASE_URL
        or not settings.model.startswith("anthropic/")
    ):
        raise ValueError("OpenRouter usage requires the Anthropic Messages URL and an anthropic/ model")
    async with create_anthropic_sdk_client(settings) as client:
        counts = []
        for text in texts:
            messages: list[MessageParam] = [{"role": "user", "content": text}]
            if openrouter_usage:
                response = await client.messages.create(
                    model=settings.model,
                    messages=messages,
                    max_tokens=1,
                    extra_body={"provider": {"only": ["Anthropic"], "allow_fallbacks": False}},
                )
                usage = response.usage
                counts.append(
                    usage.input_tokens + (usage.cache_read_input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
                )
            else:
                result = await client.messages.count_tokens(model=settings.model, messages=messages)
                counts.append(result.input_tokens)
        return counts
