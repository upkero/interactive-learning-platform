"""Anthropic token-counting adapter for the explicitly invoked calibration tool."""

from anthropic import AsyncAnthropic

from src.app.core.settings.llm import LLMSettings


async def count_provider_tokens(settings: LLMSettings, texts: list[str]) -> list[int]:
    """Call the provider; callers must authorize external requests beforehand."""
    if settings.provider != "anthropic" or settings.api_key is None:
        raise ValueError("Calibration requires the Anthropic LLM provider and its configured API key")
    client = AsyncAnthropic(api_key=settings.api_key.get_secret_value(), timeout=settings.timeout_seconds)
    try:
        counts = []
        for text in texts:
            result = await client.messages.count_tokens(
                model=settings.model, messages=[{"role": "user", "content": text}]
            )
            counts.append(result.input_tokens)
        return counts
    finally:
        await client.close()
