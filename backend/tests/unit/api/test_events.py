"""The HTTP layer must stop even if a reader emits after document_done."""

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from sse_starlette import ServerSentEvent

from src.app.api.v1.routers.events import document_events
from src.app.contracts.documents.statuses import DocumentStatus
from src.app.contracts.progress.stream_entry import StreamEntry
from src.app.contracts.users.user_record import UserRecord
from src.app.services.documents.document_query_service import DocumentQueryService
from src.app.services.progress.progress_reader import ProgressReader

pytestmark = pytest.mark.unit


class Documents:
    async def get_readable(self, *, user_id: UUID, document_id: UUID) -> tuple[SimpleNamespace, str]:
        return SimpleNamespace(status=DocumentStatus.DONE), "en"


class Reader:
    async def follow(self, *args: object, **kwargs: object) -> AsyncGenerator[StreamEntry, None]:
        yield StreamEntry("1-0", "document_done", "{}")
        yield StreamEntry("2-0", "error", "{}")


class Connected:
    async def is_disconnected(self) -> bool:
        return False


async def test_router_stops_after_document_done() -> None:
    response = await document_events(
        document_id=uuid4(),
        request=cast(Request, Connected()),
        user=cast(UserRecord, SimpleNamespace(id=uuid4())),
        documents=cast(DocumentQueryService, Documents()),
        reader=cast(ProgressReader, Reader()),
        last_event_id=None,
        last_event_id_query=None,
    )
    events = [event async for event in response.body_iterator]
    assert len(events) == 1 and isinstance(events[0], ServerSentEvent) and events[0].event == "document_done"
