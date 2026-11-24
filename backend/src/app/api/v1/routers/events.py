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
from src.app.api.v1.responses import error_responses
from src.app.contracts.progress import ProgressEventType

router = APIRouter(tags=["progress"])
_STREAM_ID = re.compile(r"^\d+-\d+$")


@router.get(
    "/documents/{document_id}/events",
    response_class=EventSourceResponse,
    operation_id="document_events",
    responses={
        200: {"content": {"text/event-stream": {}}},
        **error_responses(401, 404, 422, 500),
    },
)
async def document_events(
    document_id: UUID,
    request: Request,
    user: CurrentUserDep,
    documents: DocumentQueryServiceDep,
    reader: ProgressReaderDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    last_event_id_query: Annotated[str | None, Query(alias="last_event_id")] = None,
) -> EventSourceResponse:
    readable = await documents.get_readable(user_id=user.id, document_id=document_id)
    document, locale = readable.document, readable.owner_locale
    cursor = next(
        (value for value in (last_event_id, last_event_id_query) if value and _STREAM_ID.fullmatch(value)),
        "0-0",
    )

    async def events() -> AsyncIterator[ServerSentEvent]:
        async for entry in reader.follow(document_id, cursor, finished_status=document.status, locale=locale):
            if await request.is_disconnected():
                return
            yield ServerSentEvent(id=entry.id, event=entry.type, data=entry.data, retry=3000)
            if entry.type == ProgressEventType.DOCUMENT_DONE.value:
                return

    return EventSourceResponse(
        events(),
        ping=15,
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
