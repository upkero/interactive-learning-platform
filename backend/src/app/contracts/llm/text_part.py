"""Text part of a multimodal message."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextPart:
    text: str
