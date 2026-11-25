from functools import lru_cache

import tiktoken


class TokenCounter:
    def __init__(self, *, encoding: str = "o200k_base", calibration: float = 1.15) -> None:
        self._encoding = tiktoken.get_encoding(encoding)
        self._calibration = calibration

    def count(self, text: str) -> int:
        if not text:
            return 0
        return int(self.count_raw(text) * self._calibration) + 1

    def count_raw(self, text: str) -> int:
        """Uncalibrated tiktoken count, for calibration reports."""
        return len(self._encoding.encode(text, disallowed_special=()))


@lru_cache(maxsize=1)
def get_token_counter() -> TokenCounter:
    from src.app.core.settings.ingest import get_ingest_settings

    settings = get_ingest_settings()
    return TokenCounter(encoding=settings.tokens_encoding, calibration=settings.tokens_calibration)
