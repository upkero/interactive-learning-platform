"""Worker-facing contract for part processing pipelines."""

from typing import Protocol
from uuid import UUID


class PartPipeline(Protocol):
    async def process(self, part_id: UUID) -> None: ...
