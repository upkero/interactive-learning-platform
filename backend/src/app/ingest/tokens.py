from bisect import bisect_right
from functools import lru_cache
from typing import Protocol

import tiktoken

from src.app.core.settings.ingest import DEFAULT_TOKENS_CALIBRATION, get_ingest_settings


class TokenCounting(Protocol):
    def count(self, text: str) -> int: ...

    def chunk_spans(self, text: str, maximum: int, protected: tuple[tuple[int, int], ...]) -> list[tuple[int, int]]: ...


class TokenCounter:
    def __init__(self, *, encoding: str = "o200k_base", calibration: float = DEFAULT_TOKENS_CALIBRATION) -> None:
        self._encoding = tiktoken.get_encoding(encoding)
        self._calibration = calibration

    def count(self, text: str) -> int:
        if not text:
            return 0
        return int(self.count_raw(text) * self._calibration) + 1

    def count_raw(self, text: str) -> int:
        """Uncalibrated tiktoken count, for calibration reports."""
        return len(self._encoding.encode(text, disallowed_special=()))

    def chunk_spans(self, text: str, maximum: int, protected: tuple[tuple[int, int], ...]) -> list[tuple[int, int]]:
        tokens = self._encoding.encode(text, disallowed_special=())
        # Offsets for tokens sharing a Unicode character are identical. A
        # boundary at that offset keeps all bytes of the character together.
        _, offsets = self._encoding.decode_with_offsets(tokens)
        offsets.append(len(text))
        width = max(1, int(maximum / self._calibration))
        result: list[tuple[int, int]] = []
        index = 0
        while index < len(tokens):
            start = offsets[index]
            candidate = min(index + width, len(tokens))
            # Prefer a word boundary close to the token budget.
            for boundary in range(candidate, max(index, candidate - width // 10 - 1), -1):
                end = offsets[boundary]
                if (end == len(text) or (end > start and (text[end].isspace() or text[end - 1].isspace()))) and all(
                    not left < end < right for left, right in protected
                ):
                    candidate = boundary
                    break
            for boundary in range(candidate, index, -1):
                end = offsets[boundary]
                if end > start and all(not left < end < right for left, right in protected):
                    if self.count(text[start:end]) > maximum:
                        continue
                    result.append((start, end))
                    # Continue at the first token of the next code point.
                    index = bisect_right(offsets, end - 1, lo=index + 1)
                    break
            else:
                raise ValueError("Split limit cannot accommodate a Unicode character or protected Markdown.")
        return result


@lru_cache(maxsize=1)
def get_token_counter() -> TokenCounter:
    settings = get_ingest_settings()
    return TokenCounter(encoding=settings.tokens_encoding, calibration=settings.tokens_calibration)
