"""Deterministic fake embeddings derived from a text hash.

They are used only by the seed command with ``--fake-embeddings`` so the
demo data stays reproducible without calling a real embedding model.
"""

import hashlib
import math

from src.app.models.widget_description import EMBEDDING_DIM


def fake_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Build a unit-length vector of ``dim`` floats from ``text``."""
    anchor = hashlib.sha256(text.encode("utf-8")).digest()
    raw: list[float] = []
    counter = 0
    while len(raw) < dim:
        block = hashlib.sha256(anchor + counter.to_bytes(8, "little")).digest()
        raw.extend(byte / 127.5 - 1.0 for byte in block)
        counter += 1
    head = raw[:dim]
    norm = math.sqrt(sum(value * value for value in head))
    return [value / norm for value in head]
