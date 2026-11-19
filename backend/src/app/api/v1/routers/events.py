"""Server-sent events for document progress."""

import re
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from sse_starlette import EventSourceResponse, ServerSentEvent

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.progress import ProgressReaderDep
from src.app.api.v1.dependencies.services import DocumentQueryServiceDep

router = APIRouter(tags=["progress"])
_STREAM_ID = re.compile(r"^\d+-\d+$")


@router.get("/documents/{document_id}/events", response_class=EventSourceResponse, operation_id="document_events")
async def document_events(
    document_id: UUID,
    request: Request,
    user: CurrentUserDep,
    documents: DocumentQueryServiceDep,
    reader: ProgressReaderDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    last_event_id_query: Annotated[str | None, Query(alias="last_event_id")] = None,
) -> EventSourceResponse:
    details = await documents.get_document(user_id=user.id, document_id=document_id)
    cursor = next(
        (value for value in (last_event_id, last_event_id_query) if value and _STREAM_ID.fullmatch(value)),
        "0-0",
    )

    async def events() -> AsyncIterator[ServerSentEvent]:
        async for entry in reader.follow(document_id, cursor, finished_status=details.document.status.value):
            if await request.is_disconnected():
                return
            yield ServerSentEvent(id=entry.id, event=entry.type, data=entry.data, retry=3000)
            if entry.type == "document_done":
                return

    return EventSourceResponse(
        events(),
        ping=15,
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
