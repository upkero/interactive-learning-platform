"""Transition a document to ``failed`` and log the reason (story 1.4, 1.5).

A document becomes ``failed`` when the pipeline cannot continue: the
broker refused the task right after the commit (story 1.4, Важно 2) or
the parse pipeline hit a known error (story 1.9). The short own
transaction releases the in-processing slot, so the user can upload
again.

The public code is stored in ``documents.error_code`` and diagnostic text
in ``documents.error_detail``. The same details are emitted in one log event.
"""

import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import DocumentErrorCode, DocumentStatus
from src.app.interfaces.repositories.documents import DocumentRepositoryProtocol

logger = logging.getLogger(__name__)


async def mark_document_failed(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
    document_id: UUID,
    error_code: DocumentErrorCode,
    error_detail: str | None = None,
) -> None:
    """Set ``failed``/``error_code`` in its own transaction, then log once."""
    async with session_factory() as session, session.begin():
        await documents(session).set_status(
            document_id,
            DocumentStatus.FAILED,
            error_code=error_code,
            error_detail=error_detail,
        )
    if error_code is DocumentErrorCode.ENQUEUE_FAILED:
        return  # The dispatcher already logged the broker failure.
    logger.warning(
        "Document processing failed.",
        extra={
            "document_id": str(document_id),
            "error_code": error_code.value,
            "exception": error_detail,
        },
    )


async def mark_enqueue_failed(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
    document_id: UUID,
    error_detail: str | None = None,
) -> None:
    """Best-effort ``failed``/``enqueue_failed`` after a broker refusal.

    The caller re-raises the original 503, so a failed transition only
    logs: it must never replace the error the client already receives.
    """
    try:
        await mark_document_failed(
            session_factory=session_factory,
            documents=documents,
            document_id=document_id,
            error_code=DocumentErrorCode.ENQUEUE_FAILED,
            error_detail=error_detail,
        )
    except Exception:
        logger.exception(
            "Could not mark the document as failed after a queue error.",
            extra={
                "document_id": str(document_id),
                "error_code": DocumentErrorCode.ENQUEUE_FAILED.value,
            },
        )


__all__ = ["mark_document_failed", "mark_enqueue_failed"]
