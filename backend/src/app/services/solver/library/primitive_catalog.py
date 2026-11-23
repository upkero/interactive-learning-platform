"""In-memory set of primitive ids used by the soft search filter (2.3)."""

from collections.abc import Iterable

from src.app.contracts.widgets import PrimitiveRecord


class PrimitiveCatalog:
    """Membership check for ``primitive_hint``.

    The resolver may suggest a primitive that no longer exists in the synced
    catalog; the search then ignores the hint instead of returning nothing.
    The catalog is built once per process from ``PrimitiveRepository`` (2.4).
    """

    def __init__(self, primitive_ids: Iterable[str] = ()) -> None:
        self._ids = frozenset(primitive_ids)

    @classmethod
    def from_records(cls, records: Iterable[PrimitiveRecord]) -> "PrimitiveCatalog":
        return cls(record.id for record in records)

    @property
    def ids(self) -> frozenset[str]:
        return self._ids

    def __contains__(self, primitive_id: object) -> bool:
        return isinstance(primitive_id, str) and primitive_id in self._ids

    def __len__(self) -> int:
        return len(self._ids)


__all__ = ["PrimitiveCatalog"]
