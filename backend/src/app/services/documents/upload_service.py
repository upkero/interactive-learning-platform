"""File upload: inspect, store, create the document row (story 1.4.3).

The flow follows the story order and the acceptance criterion "when the
DB write fails, the MinIO object is deleted":

1. read the stream with the size cap and inspect the content
   (FileInspector, 1.3.3) — rejection answers 413/415/422 before
   anything is stored;
2. put the object into the ``documents`` bucket (story 1.3 key layout);
3. one transaction: processing-limit check (1.4.13, protected by the
   ``FOR UPDATE`` on the users row), ``documents`` (status ``uploaded``)
   and ``user_materials`` with ``role='owner'``;
4. only after the transaction — ``enqueue_parse`` through the
   TaskDispatcher;
5. any failure in step 3 deletes the just-uploaded object; a broker
   failure in step 4 keeps the object (a retry needs it) and moves the
   document to ``failed``/``enqueue_failed`` before the 503 is raised.
"""

import logging
from collections.abc import Callable
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import DocumentRecord, MaterialRole, SourceType
from src.app.core.settings.processing import ProcessingSettings
from src.app.exceptions.tasks import TaskDispatchError
from src.app.interfaces.repositories.documents import (
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.services.documents.document_failure import mark_enqueue_failed
from src.app.services.documents.file_inspector import FileInspector, InspectedFile, UploadStream
from src.app.services.documents.processing_capacity import assert_processing_capacity
from src.app.storage.object_keys import source_key

logger = logging.getLogger(__name__)


class UploadService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        inspector: FileInspector,
        storage: ObjectStorageClient,
        dispatcher: TaskDispatcher,
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        materials: Callable[[AsyncSession], UserMaterialRepositoryProtocol],
        users: Callable[[AsyncSession], UserRepositoryProtocol],
        settings: ProcessingSettings,
    ) -> None:
        self._session_factory = session_factory
        self._inspector = inspector
        self._storage = storage
        self._dispatcher = dispatcher
        self._documents = documents
        self._materials = materials
        self._users = users
        self._settings = settings

    async def upload(
        self,
        *,
        owner_id: UUID,
        filename: str | None,
        title: str | None,
        stream: UploadStream,
    ) -> DocumentRecord:
        # the type of the file is only known after inspection, so the
        # reader must allow the largest limit first (story 1.3.3)
        data = await self._inspector.read_with_limit(stream, max_bytes=self._inspector.max_read_bytes())
        inspected = await self._inspector.inspect(data, filename)
        document_id = uuid4()
        object_key = source_key(owner_id, document_id, inspected.extension)
        await self._storage.put_object(
            bucket="documents",
            key=object_key,
            data=data,
            content_type=inspected.mime_type,
        )
        try:
            async with self._session_factory() as session, session.begin():
                await assert_processing_capacity(
                    users=self._users(session),
                    documents=self._documents(session),
                    owner_id=owner_id,
                    limit=self._settings.max_active_documents,
                )
                document = await self._documents(session).create(
                    id=document_id,
                    owner_id=owner_id,
                    title=(title or self._title_from_filename(filename)).strip() or "Untitled",
                    source_type=SourceType.UPLOAD,
                    object_key=object_key,
                    mime_type=inspected.mime_type,
                    size_bytes=inspected.size_bytes,
                    checksum=inspected.checksum,
                    page_count=inspected.page_count,
                )
                await self._materials(session).create(
                    user_id=owner_id,
                    document_id=document.id,
                    role=MaterialRole.OWNER,
                )
        except Exception:
            # the row(s) did not stick: the object must not survive, but a
            # failing cleanup must not hide the original error
            try:
                await self._storage.delete_object(bucket="documents", key=object_key)
            except Exception:
                logger.warning("Failed to delete an orphaned upload object.", extra={"object_key": object_key})
            raise
        # network call after the transaction, never inside it
        try:
            await self._dispatcher.enqueue_parse(document.id)
        except TaskDispatchError as exc:
            # the row is committed, so the document must not hang in
            # "uploaded": failed/enqueue_failed releases the limit slot and
            # lets the client retry. The stored object stays for that retry.
            await mark_enqueue_failed(
                session_factory=self._session_factory,
                documents=self._documents,
                document_id=document.id,
                error_detail=repr(exc.__cause__ or exc),
            )
            raise
        return document

    @staticmethod
    def _title_from_filename(filename: str | None) -> str:
        if not filename:
            return "Untitled"
        return filename.rsplit(".", 1)[0]


__all__ = ["InspectedFile", "UploadService"]
