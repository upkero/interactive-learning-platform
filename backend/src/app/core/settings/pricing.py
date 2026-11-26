"""Model prices used for observability reports (USD per million tokens)."""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("grasp.pricing")
_warned: set[str] = set()


@dataclass(frozen=True, slots=True)
class ModelPricing:
    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0


_PRICES: dict[str, ModelPricing] = {
    "llama3.2": ModelPricing(),
    "claude-3-5-sonnet": ModelPricing(input=3.0, output=15.0, cache_read=0.3, cache_write=3.75),
    "claude-sonnet-5-5": ModelPricing(input=2.0, output=10.0, cache_read=0.1, cache_write=2.5),
}


def get_model_pricing(model: str) -> ModelPricing | None:
    normalized = model.removeprefix("anthropic/")
    normalized = re.sub(r"-\d{8}$", "", normalized)
    if normalized.startswith("claude-"):
        normalized = normalized.replace(".", "-")
    price = _PRICES.get(normalized)
    if price is None and model not in _warned:
        _warned.add(model)
        logger.warning("pricing.unknown_model", extra={"model": model})
    return price
