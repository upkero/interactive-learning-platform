"""Integration tests 1.4.3: upload and read of documents over the real API.

Runs against real Postgres and MinIO; the TaskDispatcher is replaced by
the recording fake (the broker is not part of this story). Acceptance:
a PDF upload creates the object in MinIO and the row in the DB, the
fake dispatcher receives ``enqueue_parse``, and a foreign document is
indistinguishable from a missing one (404).
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.api.v1.dependencies.services import get_task_dispatcher
from src.app.api.v1.middleware.rate_limit import limiter
from src.app.bootstrap.container import ApplicationContainer
from src.app.repositories.document_repository import DocumentRepository
from src.main import create_app
from tests.support.fakes.tasks import FakeTaskDispatcher

pytestmark = pytest.mark.integration

_PDF_PATH = Path(__file__).resolve().parents[2] / "support" / "fixtures" / "files" / "sample.pdf"
_PDF_BYTES = _PDF_PATH.read_bytes()
_DOCX_BYTES = (_PDF_PATH.parent / "sample.docx").read_bytes()
_MD_BYTES = b"# Notes\n\nSome markdown content for the title test.\n"


@pytest.fixture
def dispatcher() -> FakeTaskDispatcher:
    return FakeTaskDispatcher()


@pytest.fixture
def client(dispatcher: FakeTaskDispatcher) -> Iterator[TestClient]:
    limiter.reset()
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        app = cast(FastAPI, test_client.app)
        app.dependency_overrides[get_task_dispatcher] = lambda: dispatcher
        yield test_client


def _register(client: TestClient, email: str | None = None) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email or f"user-{uuid4()}@example.com", "password": "long-enough-password"},
    )
    assert response.status_code == 201, response.text


def _upload(
    client: TestClient,
    *,
    filename: str = "lecture.pdf",
    title: str | None = None,
) -> Any:
    content_type = "application/pdf"
    if filename.endswith((".md", ".markdown")):
        content_type = "text/markdown"
    elif filename.endswith(".docx"):
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    content = _PDF_BYTES
    if filename.endswith((".md", ".markdown")):
        content = _MD_BYTES
    elif filename.endswith(".docx"):
        content = _DOCX_BYTES
    files = {"file": (filename, content, content_type)}
    data = {"title": title} if title is not None else None
    return client.post("/api/v1/documents", files=files, data=data)


async def test_upload_creates_minio_object_db_row_and_dispatches(
    client: TestClient, dispatcher: FakeTaskDispatcher, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _register(client)
    response = _upload(client)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "uploaded"

    document_id = UUID(created["id"])

    # the fake dispatcher received the parse task after the commit
    assert dispatcher.calls == [("enqueue_parse", (document_id,))]

    # the DB row: uploaded, inspected content metadata
    async with session_factory() as session:
        record = await DocumentRepository(session).get(document_id)
    assert record is not None
    assert record.status.value == "uploaded"
    assert record.mime_type == "application/pdf"
    assert record.page_count is not None
    assert record.checksum
    assert record.object_key.startswith("docs/")
    assert record.object_key.endswith(".pdf")

    # the object really is in the documents bucket
    container = cast(ApplicationContainer, cast(FastAPI, client.app).state.container)
    stored = await container.object_storage.get_object(bucket="documents", key=record.object_key)
    assert stored == _PDF_BYTES

    # reading it back: DocumentOut contract
    shown = client.get(f"/api/v1/documents/{document_id}")
    assert shown.status_code == 200
    body = shown.json()
    assert body["id"] == str(document_id)
    assert body["title"] == "lecture"
    assert body["status"] == "uploaded"
    assert body["role"] == "owner"
    assert body["parts"] == []
    assert body["shared_with"] == []
    # presigned source link to the stored object
    assert body["source_url"] is not None
    assert record.object_key in body["source_url"]


async def test_upload_titles_are_explicit_or_from_the_filename(client: TestClient) -> None:
    _register(client)
    titled = _upload(client, filename="notes.md", title="My Notes")
    assert titled.status_code == 201, titled.text
    shown = client.get(f"/api/v1/documents/{titled.json()['id']}")
    assert shown.status_code == 200
    assert shown.json()["title"] == "My Notes"

    default = _upload(client, filename="report-v2.docx")
    assert default.status_code == 201, default.text
    shown = client.get(f"/api/v1/documents/{default.json()['id']}")
    assert shown.status_code == 200
    assert shown.json()["title"] == "report-v2"


async def test_foreign_document_is_404(client: TestClient) -> None:
    _register(client, f"owner-{uuid4()}@example.com")
    created = _upload(client)
    assert created.status_code == 201

    # a different user: clear the cookie and register fresh
    client.cookies.clear()
    _register(client, f"stranger-{uuid4()}@example.com")

    shown = client.get(f"/api/v1/documents/{created.json()['id']}")
    assert shown.status_code == 404
    assert shown.json()["error_code"] == "document_not_found"


async def test_unknown_document_is_404(client: TestClient) -> None:
    _register(client)
    shown = client.get(f"/api/v1/documents/{uuid4()}")
    assert shown.status_code == 404
    assert shown.json()["error_code"] == "document_not_found"


async def test_upload_without_a_cookie_is_401(client: TestClient) -> None:
    response = _upload(client)
    assert response.status_code == 401
    assert response.json()["error_code"] == "not_authenticated"


async def test_import_creates_document_and_dispatches(client: TestClient, dispatcher: FakeTaskDispatcher) -> None:
    _register(client)
    response = client.post(
        "/api/v1/documents/import",
        json={"url": "https://docs.google.com/document/d/1AbC_dEf-123/edit"},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "uploaded"
    document_id = UUID(created["id"])

    assert dispatcher.calls == [("enqueue_parse", (document_id,))]

    shown = client.get(f"/api/v1/documents/{document_id}")
    assert shown.status_code == 200
    body = shown.json()
    assert body["title"] == "Untitled"
    assert body["status"] == "uploaded"
    assert body["role"] == "owner"
    # for gdocs the source link is the original import link
    assert body["source_url"] == "https://docs.google.com/document/d/1AbC_dEf-123/edit"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/document/d/1AbC/edit",
        "https://docs.google.com/spreadsheets/d/1AbC/edit",
        "https://docs.google.com/presentation/d/1AbC/edit",
        "https://docs.google.com/document/edit/1AbC",
        "not a link at all",
    ],
)
async def test_invalid_import_link_is_422(client: TestClient, dispatcher: FakeTaskDispatcher, url: str) -> None:
    _register(client)
    response = client.post("/api/v1/documents/import", json={"url": url})
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_gdocs_url"
    assert dispatcher.calls == []


async def test_import_counts_towards_the_processing_limit(client: TestClient) -> None:
    _register(client)
    first = client.post("/api/v1/documents/import", json={"url": "https://docs.google.com/document/d/first/edit"})
    second = _upload(client, filename="second.pdf")
    assert first.status_code == 201 and second.status_code == 201
    third = client.post("/api/v1/documents/import", json={"url": "https://docs.google.com/document/d/third/edit"})
    assert third.status_code == 429
    assert third.json()["error_code"] == "processing_limit_reached"


async def test_the_third_upload_in_processing_is_429(
    client: TestClient, dispatcher: FakeTaskDispatcher, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _register(client)
    first = _upload(client, filename="first.pdf")
    second = _upload(client, filename="second.pdf")
    assert first.status_code == 201 and second.status_code == 201
    assert dispatcher.calls == [
        ("enqueue_parse", (UUID(first.json()["id"]),)),
        ("enqueue_parse", (UUID(second.json()["id"]),)),
    ]

    third = _upload(client, filename="third.pdf")
    assert third.status_code == 429
    assert third.json()["error_code"] == "processing_limit_reached"

    # the first document still reads fine; the user has two in processing
    first_document_id = UUID(first.json()["id"])
    shown = client.get(f"/api/v1/documents/{first_document_id}")
    assert shown.status_code == 200
    async with session_factory() as session:
        record = await DocumentRepository(session).get(first_document_id)
    assert record is not None
    async with session_factory() as session:
        assert await DocumentRepository(session).count_active(record.owner_id) == 2
