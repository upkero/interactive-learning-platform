"""Record completion notifications sent by processing services."""

from uuid import UUID


class FakeDocumentNotifications:
    def __init__(self) -> None:
        self.completed: list[UUID] = []

    async def on_document_finished(self, document_id: UUID) -> None:
        self.completed.append(document_id)
