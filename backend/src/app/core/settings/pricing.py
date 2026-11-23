"""Model prices used for observability reports (USD per million tokens)."""

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class ModelPricing:
    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0


_PRICES: dict[str, ModelPricing] = {
    "llama3.2": ModelPricing(),
    "claude-3-5-sonnet-20241022": ModelPricing(input=3.0, output=15.0, cache_read=0.3, cache_write=3.75),
}


@lru_cache(maxsize=1)
def get_model_pricing(model: str) -> ModelPricing:
    return _PRICES.get(model, ModelPricing())
