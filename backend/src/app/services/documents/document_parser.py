"""Explicit placeholder for the document parser provided by story 1.9."""

from uuid import UUID


class DocumentParser:
    """Define the worker-facing parser entry point until story 1.9."""

    async def parse(self, document_id: UUID) -> None:
        raise NotImplementedError("Document parsing is not implemented until story 1.9")
