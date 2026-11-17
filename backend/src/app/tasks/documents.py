"""Document task entry point; parsing is implemented in story 1.9."""

from uuid import UUID

from src.app.tasks.names import PARSE_DOCUMENT_TASK
from src.app.tasks.runner import run_async
from src.worker import celery_app


@celery_app.task(name=PARSE_DOCUMENT_TASK, soft_time_limit=600, time_limit=660)  # type: ignore[untyped-decorator]
def parse_document(document_id: str) -> None:
    document_uuid = UUID(document_id)
    run_async(lambda container: container.document_parser.parse(document_uuid), document_id=document_id)
