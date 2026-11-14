"""File upload: inspect, store, create the document row (story 1.4.3).

The flow follows the story order and the acceptance criterion "when the
DB write fails, the MinIO object is deleted":

1. read the stream with the size cap and inspect the content
   (FileInspector, 1.3.3) — rejection answers 413/415/422 before
   anything is stored;
2. put the object into the ``documents`` bucket;
3. one transaction: processing-limit check (1.4.13, protected by the
   ``FOR UPDATE`` on the users row), ``documents`` (status ``uploaded``)
   and ``user_materials`` with ``role='owner'``, commit;
4. only after commit — ``enqueue_parse`` through the TaskDispatcher;
5. any failure in step 3 deletes the just-uploaded object.
"""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents import DocumentRecord, MaterialRole, SourceType
from src.app.interfaces.repositories.documents import (
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.services.documents.file_inspector import FileInspector, InspectedFile, UploadStream
from src.app.services.documents.processing_limits import assert_processing_capacity


class UploadService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        inspector: FileInspector,
        storage: ObjectStorageClient,
        dispatcher: TaskDispatcher,
        documents: DocumentRepositoryProtocol,
        materials: UserMaterialRepositoryProtocol,
        users: UserRepositoryProtocol,
    ) -> None:
        self._session = session
        self._inspector = inspector
        self._storage = storage
        self._dispatcher = dispatcher
        self._documents = documents
        self._materials = materials
        self._users = users

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
        object_key = f"docs/{uuid4()}.{inspected.extension}"
        await self._storage.put_object(
            bucket="documents",
            key=object_key,
            data=data,
            content_type=inspected.mime_type,
        )
        try:
            await assert_processing_capacity(
                users=self._users,
                documents=self._documents,
                owner_id=owner_id,
            )
            document = await self._documents.create(
                owner_id=owner_id,
                title=(title or self._title_from_filename(filename)).strip() or "Untitled",
                source_type=SourceType.UPLOAD,
                object_key=object_key,
                mime_type=inspected.mime_type,
                size_bytes=inspected.size_bytes,
                checksum=inspected.checksum,
                page_count=inspected.page_count,
            )
            await self._materials.create(
                user_id=owner_id,
                document_id=document.id,
                role=MaterialRole.OWNER,
            )
            await self._session.commit()
        except Exception:
            # the row(s) did not stick: the object must not survive
            await self._session.rollback()
            await self._storage.delete_object(bucket="documents", key=object_key)
            raise
        # network call after commit, never inside the transaction
        await self._dispatcher.enqueue_parse(document.id)
        return document

    @staticmethod
    def _title_from_filename(filename: str | None) -> str:
        if not filename:
            return "Untitled"
        return filename.rsplit(".", 1)[0]


__all__ = ["InspectedFile", "UploadService"]
