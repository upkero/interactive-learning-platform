"""Immutable node of the parsed topic tree (contract of story 1.9).

The parser writes ``documents.topic_tree`` as a list of root nodes; the
API never recalculates levels or token sums — both come from the parse
result as is. ``total_tokens`` is what the client sees as
``TopicNodeOut.tokens``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TopicNode:
    id: str
    title: str
    level: int
    start: int
    end: int
    own_tokens: int
    total_tokens: int
    page: int | None = None
    image_ids: tuple[str, ...] = ()
    children: tuple["TopicNode", ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this contract for JSON storage."""
        return asdict(self)

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> "TopicNode":
        """Build a node from the JSONB payload, tolerant to older rows."""
        return cls(
            id=str(raw["id"]),
            title=str(raw["title"]),
            level=int(raw.get("level", 1)),
            start=int(raw.get("start", 0)),
            end=int(raw.get("end", 0)),
            own_tokens=int(raw.get("own_tokens", 0)),
            total_tokens=int(raw.get("total_tokens", raw.get("tokens", 0))),
            page=int(raw["page"]) if raw.get("page") is not None else None,
            image_ids=tuple(str(image_id) for image_id in raw.get("image_ids", ())),
            children=tuple(cls.from_raw(child) for child in raw.get("children", ())),
        )


def topic_roots(raw: Any) -> tuple[TopicNode, ...]:
    """Parse the stored JSONB value into root nodes.

    The current contract is a list of roots; the ``{"topics": [...]}``
    wrapper of early seeds is still accepted so old rows keep reading.
    """
    if raw is None:
        return ()
    roots: Sequence[Any] = raw["topics"] if isinstance(raw, Mapping) else raw
    return tuple(TopicNode.from_raw(node) for node in roots)


__all__ = ["TopicNode", "topic_roots"]
