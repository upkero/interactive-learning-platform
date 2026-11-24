"""The HTTP layer must stop even if a reader emits after document_done."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from sse_starlette import ServerSentEvent

from src.app.api.v1.routers.events import document_events
from src.app.contracts.documents import DocumentRecord, ReadableDocument
from src.app.contracts.documents.statuses import DocumentStatus, SourceType
from src.app.contracts.progress.stream_entry import StreamEntry
from src.app.contracts.users.user_record import UserRecord
from src.app.services.documents.document_query_service import DocumentQueryService
from src.app.services.progress.progress_reader import ProgressReader

pytestmark = pytest.mark.unit


class Documents:
    async def get_readable(self, *, user_id: UUID, document_id: UUID) -> ReadableDocument:
        now = datetime.now(UTC)
        return ReadableDocument(
            DocumentRecord(
                id=document_id,
                owner_id=user_id,
                title="test",
                source_type=SourceType.UPLOAD,
                source_uri=None,
                object_key="test.md",
                mime_type="text/markdown",
                size_bytes=1,
                page_count=None,
                checksum="a" * 64,
                status=DocumentStatus.DONE,
                topic_tree=None,
                error_code=None,
                created_at=now,
                updated_at=now,
            ),
            "en",
            "ready",
        )


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
        user=UserRecord(
            id=uuid4(),
            email="test@example.com",
            password_hash="hash",
            display_name=None,
            locale="en",
            monthly_limit=20,
            period_anchor=None,
            profile={},
            notify_email=True,
            created_at=datetime.now(UTC),
        ),
        documents=cast(DocumentQueryService, Documents()),
        reader=cast(ProgressReader, Reader()),
        last_event_id=None,
        last_event_id_query=None,
    )
    events = [event async for event in response.body_iterator]
    assert len(events) == 1 and isinstance(events[0], ServerSentEvent) and events[0].event == "document_done"
