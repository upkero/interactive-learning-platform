"""Unit tests 1.4.4: ImportService with fakes — the API never goes online."""

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents import DocumentStatus, MaterialRole, SourceType
from src.app.exceptions.documents import InvalidGdocsUrlError, ProcessingLimitError
from src.app.services.documents.import_service import ImportService, extract_gdocs_id
from tests.support.fakes.repositories.documents import (
    FakeDocumentRepository,
    FakeUserMaterialRepository,
)
from tests.support.fakes.repositories.users import FakeUserRepository
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient
from tests.support.fakes.tasks import FakeTaskDispatcher

pytestmark = pytest.mark.unit

_VALID_URL = "https://docs.google.com/document/d/1AbC_dEf-123/edit"


class _FakeSession:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _service(
    *,
    documents: FakeDocumentRepository | None = None,
) -> tuple[
    ImportService,
    FakeDocumentRepository,
    FakeUserMaterialRepository,
    FakeObjectStorageClient,
    FakeTaskDispatcher,
]:
    documents = documents or FakeDocumentRepository()
    materials = FakeUserMaterialRepository()
    storage = FakeObjectStorageClient()
    dispatcher = FakeTaskDispatcher()
    service = ImportService(
        session=cast(AsyncSession, _FakeSession()),
        dispatcher=dispatcher,
        documents=documents,
        materials=materials,
        users=FakeUserRepository(),
    )
    return service, documents, materials, storage, dispatcher


def test_extract_gdocs_id_accepts_document_links_with_any_trailing_path() -> None:
    assert extract_gdocs_id(_VALID_URL) == "1AbC_dEf-123"
    assert extract_gdocs_id("https://docs.google.com/document/d/xyz987/view") == "xyz987"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/document/d/1AbC/edit",
        "https://docs.google.com/spreadsheets/d/1AbC/edit",  # Sheets
        "https://docs.google.com/presentation/d/1AbC/edit",  # Slides
        "https://docs.google.com/document/edit/1AbC",  # no /d/ segment
        "http://docs.google.com/document/d/1AbC/edit",  # not https
        "just a phrase",
        "",
    ],
)
def test_extract_gdocs_id_rejects_foreign_links(url: str) -> None:
    with pytest.raises(InvalidGdocsUrlError) as exc_info:
        extract_gdocs_id(url)
    assert exc_info.value.error_code == "invalid_gdocs_url"


async def test_valid_link_creates_rows_and_dispatches() -> None:
    service, _documents, materials, storage, dispatcher = _service()
    owner = uuid4()

    document = await service.import_document(owner_id=owner, url=_VALID_URL)

    assert document.status is DocumentStatus.UPLOADED
    assert document.source_type is SourceType.GDOCS
    assert document.source_uri == _VALID_URL
    assert document.title == "Untitled"

    assert await materials.get_role(owner, document.id) is MaterialRole.OWNER
    assert dispatcher.calls == [("enqueue_parse", (document.id,))]
    # the API must not touch the network or the object storage
    assert not storage.put_object_calls
    assert not storage.delete_object_calls


async def test_invalid_link_creates_nothing() -> None:
    for url in ("https://example.com/doc", "https://docs.google.com/spreadsheets/d/1/edit"):
        service, documents, materials, _storage, dispatcher = _service()
        with pytest.raises(InvalidGdocsUrlError):
            await service.import_document(owner_id=uuid4(), url=url)
        assert not documents._documents
        assert not materials._materials
        assert dispatcher.calls == []


async def test_the_third_import_in_processing_is_rejected() -> None:
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

    service, _documents, _materials, _storage, dispatcher = _service(documents=documents)
    with pytest.raises(ProcessingLimitError) as exc_info:
        await service.import_document(owner_id=owner, url=_VALID_URL)

    assert exc_info.value.error_code == "processing_limit_reached"
    assert dispatcher.calls == []
