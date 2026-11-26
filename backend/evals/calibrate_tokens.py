"""Measure the 95th-percentile calibration against Anthropic on ten UTF-8 documents.

Run only with permission to contact the external API: python -m evals.calibrate_tokens FILE ...
Configure LLM_PROVIDER=anthropic, LLM_MODEL and the API key outside version control.
Use --openrouter-usage explicitly to count billed input tokens via one-token requests.
"""

import asyncio
import math
from argparse import ArgumentParser
from pathlib import Path

from src.app.core.settings.llm import get_llm_settings
from src.app.ingest.tokens import TokenCounter
from src.app.llm.token_calibration import count_provider_tokens


async def main(paths: list[str], *, openrouter_usage: bool = False) -> None:
    if len(paths) != 10:
        raise ValueError("Provide exactly ten representative Russian and English UTF-8 documents")
    texts = [await asyncio.to_thread(Path(path).read_text, encoding="utf-8") for path in paths]
    counter = TokenCounter(calibration=1.0)
    raw = [counter.count_raw(text) for text in texts]
    if any(count == 0 for count in raw):
        raise ValueError("Calibration documents must not be empty")
    settings = get_llm_settings()
    actual = await count_provider_tokens(settings, texts, openrouter_usage=openrouter_usage)
    ratios = sorted(provider / estimate for provider, estimate in zip(actual, raw, strict=True))
    coefficient = ratios[math.ceil(len(ratios) * 0.95) - 1]
    method = "OpenRouter messages.create usage" if openrouter_usage else "Anthropic messages.count_tokens"
    print(f"Model: {settings.model}. Method: {method}.")
    for path, estimate, provider in zip(paths, raw, actual, strict=True):
        print(f"{path}: tiktoken={estimate}, provider={provider}, ratio={provider / estimate:.4f}")
    print(f"TOKENS_CALIBRATION={math.ceil(coefficient * 10000) / 10000:.4f}")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--openrouter-usage", action="store_true", help="Use billed input usage via OpenRouter.")
    parser.add_argument("files", nargs=10, help="Ten representative Russian and English UTF-8 documents.")
    args = parser.parse_args()
    asyncio.run(main(args.files, openrouter_usage=args.openrouter_usage))
