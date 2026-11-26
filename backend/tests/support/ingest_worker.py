"""Real prefork broker probe: the parser stalls *after* the parsing commit."""

import time
from uuid import UUID

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.ingest import ParsedDocument
from src.app.core.settings.ingest import IngestSettings
from src.app.core.settings.upload import UploadSettings
from src.app.db.parsing_lease import PostgresParsingLease
from src.app.ingest.images import ImageStore
from src.app.ingest.parsers.base import DocumentParser, ParserRegistry
from src.app.ingest.parsers.gdocs_importer import GDocsImporter
from src.app.ingest.tokens import TokenCounter
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.services.documents.document_ingest_runner import DocumentIngestRunner
from src.app.services.documents.document_ingest_service import DocumentIngestService
from src.app.services.documents.file_inspector import FileInspector
from src.app.tasks.runner import run_async
from src.worker import celery_app
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient


class StallParser(DocumentParser):
    supported_mime_types = frozenset({"text/plain"})

    def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
        while True:
            time.sleep(1)


@celery_app.task(name="tests.ingest_stall")  # type: ignore[untyped-decorator]
def stall(document_id: str) -> None:
    async def parse(container: ApplicationContainer) -> None:
        storage = FakeObjectStorageClient(objects={("documents", "stall.txt"): b"text"})
        lease = PostgresParsingLease(container._db_engine)
        service = DocumentIngestService(
            session_factory=container.session_factory,
            documents=DocumentRepository,
            images=ImageRepository,
            storage=storage,
            registry=ParserRegistry((StallParser(),)),
            notifier=container.progress_notifier,
            gdocs=GDocsImporter(max_bytes=1024),
            parsing_lease=lease,
            image_store=ImageStore(storage),
            inspector=FileInspector(UploadSettings()),
            counter=TokenCounter(),
            ingest_settings=IngestSettings(),
            upload_settings=UploadSettings(),
        )
        runner = DocumentIngestRunner(
            lease=lease,
            build=lambda: service,
            session_factory=container.session_factory,
            documents=DocumentRepository,
            notifier=container.progress_notifier,
        )
        await runner.parse(UUID(document_id))

    run_async(parse, document_id=document_id)
