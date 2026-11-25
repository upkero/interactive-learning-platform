"""Guard ingestion, including dependency initialization, with the same lease."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import DocumentErrorCode
from src.app.contracts.progress.event_type import ProgressEventType
from src.app.interfaces.repositories.documents import DocumentRepositoryProtocol
from src.app.interfaces.services.ingest import ParsingLease
from src.app.interfaces.services.progress_notifier import ProgressNotifier
from src.app.services.documents.document_failure import mark_document_failed
from src.app.services.documents.document_ingest_service import DocumentIngestService


class DocumentIngestRunner:
    def __init__(
        self,
        *,
        lease: ParsingLease,
        build: Callable[[], DocumentIngestService],
        session_factory: async_sessionmaker[AsyncSession],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        notifier: ProgressNotifier,
    ) -> None:
        self._lease = lease
        self._build = build
        self._session_factory = session_factory
        self._documents = documents
        self._notifier = notifier

    async def parse(self, document_id: UUID) -> None:
        async with self._lease.acquire(document_id) as acquired:
            if not acquired:
                return
            try:
                service = self._build()
            except Exception as exc:
                async with self._session_factory() as session, session.begin():
                    document = await self._documents(session).begin_parsing(document_id)
                if document is not None:
                    await mark_document_failed(
                        session_factory=self._session_factory,
                        documents=self._documents,
                        document_id=document_id,
                        error_code=DocumentErrorCode.PARSE_FAILED,
                        error_detail=type(exc).__name__,
                    )
                    await self._notifier.emit(
                        document_id,
                        ProgressEventType.ERROR,
                        stage="parsing",
                        message="Document parsing failed",
                        error_code=DocumentErrorCode.PARSE_FAILED,
                    )
                return
            await service._parse_locked(document_id)
