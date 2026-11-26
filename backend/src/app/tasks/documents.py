"""Celery entry point for document ingestion."""

from uuid import UUID

from src.app.bootstrap.container import ApplicationContainer
from src.app.tasks.names import PARSE_DOCUMENT_TASK
from src.app.tasks.runner import run_async
from src.worker import celery_app


@celery_app.task(name=PARSE_DOCUMENT_TASK, soft_time_limit=600, time_limit=660)  # type: ignore[untyped-decorator]
def parse_document(document_id: str) -> None:
    document_uuid = UUID(document_id)

    async def parse(container: ApplicationContainer) -> None:
        await container.document_ingest_runner.parse(document_uuid)

    run_async(parse, document_id=document_id)
