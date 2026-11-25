"""Celery entry point for document ingestion."""

from uuid import UUID

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents.statuses import DocumentErrorCode
from src.app.repositories.document_repository import DocumentRepository
from src.app.services.documents.document_failure import mark_document_failed
from src.app.tasks.names import PARSE_DOCUMENT_TASK
from src.app.tasks.runner import run_async
from src.worker import celery_app


@celery_app.task(name=PARSE_DOCUMENT_TASK, soft_time_limit=600, time_limit=660)  # type: ignore[untyped-decorator]
def parse_document(document_id: str) -> None:
    document_uuid = UUID(document_id)

    async def parse(container: ApplicationContainer) -> None:
        try:
            ingest = container.document_ingest
        except Exception as exc:
            async with container.session_factory() as session, session.begin():
                document = await DocumentRepository(session).begin_parsing(document_uuid)
            if document is None:
                return
            await mark_document_failed(
                session_factory=container.session_factory,
                documents=DocumentRepository,
                document_id=document_uuid,
                error_code=DocumentErrorCode.PARSE_FAILED,
                error_detail=type(exc).__name__,
            )
            return
        await ingest.parse(document_uuid)

    run_async(parse, document_id=document_id)
