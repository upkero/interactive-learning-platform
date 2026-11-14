"""Unit tests 1.4.3: UploadService with fakes — no network, no database."""

import hashlib
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents import DocumentStatus, MaterialRole, SourceType
from src.app.core.settings.upload import get_upload_settings
from src.app.exceptions.documents import ProcessingLimitError
from src.app.services.documents.file_inspector import FileInspector
from src.app.services.documents.upload_service import UploadService
from tests.support.fakes.repositories.documents import (
    FakeDocumentRepository,
    FakeUserMaterialRepository,
)
from tests.support.fakes.repositories.users import FakeUserRepository
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient
from tests.support.fakes.tasks import FakeTaskDispatcher

pytestmark = pytest.mark.unit

# a real (tiny but valid) PDF from the story 1.3 fixtures
_PDF_PATH = Path(__file__).resolve().parents[3] / "support" / "fixtures" / "files" / "sample.pdf"
_PDF_BYTES = _PDF_PATH.read_bytes()


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self._rollback_targets: list[object] = []

    def on_rollback(self, *targets: object) -> None:
        self._rollback_targets.extend(targets)

    async def commit(self) -> None:
        self.committed = True
        self._rollback_targets.clear()

    async def rollback(self) -> None:
        self.rolled_back = True
        for target in self._rollback_targets:
            target.rollback()  # type: ignore[attr-defined]


class _Stream:
    """Minimal UploadStream over fixed bytes (one read, then EOF)."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._read = False

    async def read(self, size: int) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._data


def _service(
    *,
    documents: FakeDocumentRepository | None = None,
    materials: FakeUserMaterialRepository | None = None,
) -> tuple[
    UploadService,
    FakeDocumentRepository,
    FakeUserMaterialRepository,
    FakeObjectStorageClient,
    FakeTaskDispatcher,
    _FakeSession,
]:
    session = _FakeSession()
    documents = documents or FakeDocumentRepository()
    materials = materials or FakeUserMaterialRepository()
    storage = FakeObjectStorageClient()
    dispatcher = FakeTaskDispatcher()
    session.on_rollback(documents, materials)
    service = UploadService(
        session=cast(AsyncSession, session),
        inspector=FileInspector(get_upload_settings()),
        storage=storage,
        dispatcher=dispatcher,
        documents=documents,
        materials=materials,
        users=FakeUserRepository(),
    )
    return service, documents, materials, storage, dispatcher, session


async def test_pdf_upload_stores_object_and_creates_rows_and_dispatches() -> None:
    service, documents, materials, storage, dispatcher, session = _service()
    owner = uuid4()

    document = await service.upload(
        owner_id=owner,
        filename="lecture.pdf",
        title=None,
        stream=_Stream(_PDF_BYTES),
    )

    assert document.status is DocumentStatus.UPLOADED
    assert document.title == "lecture"
    assert document.mime_type == "application/pdf"
    assert document.checksum == hashlib.sha256(_PDF_BYTES).hexdigest()
    assert document.size_bytes == len(_PDF_BYTES)
    assert document.page_count is not None

    assert len(storage.put_object_calls) == 1
    bucket, key, data, content_type = storage.put_object_calls[0]
    assert bucket == "documents"
    assert key.startswith("docs/") and key.endswith(".pdf")
    assert key == document.object_key
    assert data == _PDF_BYTES
    assert content_type == "application/pdf"

    assert await documents.get(document.id) is not None
    assert await materials.get_role(owner, document.id) is MaterialRole.OWNER
    assert session.committed is True
    assert dispatcher.calls == [("enqueue_parse", (document.id,))]


async def test_db_failure_deletes_the_uploaded_object() -> None:
    class _BrokenMaterials(FakeUserMaterialRepository):
        async def create(  # type: ignore[override]
            self,
            *,
            user_id: UUID,
            document_id: UUID,
            role: MaterialRole,
            shared_by: UUID | None = None,
        ) -> object:
            raise RuntimeError("database exploded")

    service, documents, _materials, storage, dispatcher, session = _service(materials=_BrokenMaterials())

    with pytest.raises(RuntimeError):
        await service.upload(
            owner_id=uuid4(),
            filename="lecture.pdf",
            title=None,
            stream=_Stream(_PDF_BYTES),
        )

    uploaded_bucket, uploaded_key = storage.put_object_calls[0][:2]
    assert storage.delete_object_calls == [(uploaded_bucket, uploaded_key)]
    assert not documents._documents
    assert dispatcher.calls == []
    assert session.rolled_back is True


async def test_third_document_in_processing_is_rejected() -> None:
    documents = FakeDocumentRepository()
    owner = uuid4()
    for status in (DocumentStatus.UPLOADED, DocumentStatus.PARSING):
        record = await documents.create(
            owner_id=owner,
            title=f"doc-{status}",
            source_type=SourceType.UPLOAD,
            object_key=f"docs/{uuid4()}.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="c" * 64,
        )
        await documents.set_status(record.id, status)

    service, _documents, _materials, storage, dispatcher, _session = _service(documents=documents)
    with pytest.raises(ProcessingLimitError) as exc_info:
        await service.upload(
            owner_id=owner,
            filename="third.pdf",
            title=None,
            stream=_Stream(_PDF_BYTES),
        )

    assert exc_info.value.error_code == "processing_limit_reached"
    assert exc_info.value.extra == {"limit": 2}
    # the object of the rejected upload must not survive
    uploaded_bucket, uploaded_key = storage.put_object_calls[0][:2]
    assert storage.delete_object_calls == [(uploaded_bucket, uploaded_key)]
    assert dispatcher.calls == []


async def test_parsed_documents_do_not_block_the_limit() -> None:
    documents = FakeDocumentRepository()
    owner = uuid4()
    for _ in range(2):
        record = await documents.create(
            owner_id=owner,
            title="idle",
            source_type=SourceType.UPLOAD,
            object_key=f"docs/{uuid4()}.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="c" * 64,
        )
        await documents.set_status(record.id, DocumentStatus.PARSED)

    service, _documents, _materials, _storage, dispatcher, _session = _service(documents=documents)
    document = await service.upload(
        owner_id=owner,
        filename="third.pdf",
        title=None,
        stream=_Stream(_PDF_BYTES),
    )
    assert document.status is DocumentStatus.UPLOADED
    assert dispatcher.calls == [("enqueue_parse", (document.id,))]


async def test_other_users_documents_do_not_block_the_limit() -> None:
    documents = FakeDocumentRepository()
    for _ in range(3):
        await documents.create(
            owner_id=uuid4(),
            title="foreign",
            source_type=SourceType.UPLOAD,
            object_key=f"docs/{uuid4()}.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="c" * 64,
        )

    service, _documents, _materials, _storage, _dispatcher, _session = _service(documents=documents)
    document = await service.upload(
        owner_id=uuid4(),
        filename="mine.pdf",
        title=None,
        stream=_Stream(_PDF_BYTES),
    )
    assert document.status is DocumentStatus.UPLOADED


async def test_unsupported_content_is_rejected_before_anything_is_stored() -> None:
    service, _documents, _materials, storage, dispatcher, _session = _service()
    with pytest.raises(Exception) as exc_info:
        await service.upload(
            owner_id=uuid4(),
            filename="song.mp3",
            title=None,
            stream=_Stream(b"ID3 not a document"),
        )
    assert exc_info.value.error_code == "unsupported_file_type"  # type: ignore[attr-defined]
    assert not storage.put_object_calls
    assert dispatcher.calls == []
