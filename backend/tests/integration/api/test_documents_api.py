"""Integration tests 1.4.3: upload and read of documents over the real API.

Runs against real Postgres and MinIO; the TaskDispatcher is replaced by
the recording fake (the broker is not part of this story). Acceptance:
a PDF upload creates the object in MinIO and the row in the DB, the
fake dispatcher receives ``enqueue_parse``, and a foreign document is
indistinguishable from a missing one (404).
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.api.v1.middleware.rate_limit import limiter
from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents import DocumentStatus, MaterialRole, PartDraft, SourceType
from src.app.contracts.quota import LedgerOp
from src.app.contracts.widgets import UsageStatus, WidgetKind, WidgetUsageDraft
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.models.quiz_attempt import QuizAttempt
from src.app.models.report import Report
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
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
        container = cast(ApplicationContainer, app.state.container)
        # the real dispatcher would need a broker; services take it from here
        container.__dict__["task_dispatcher"] = dispatcher
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
    assert record.object_key == f"{record.owner_id}/{document_id}/source.pdf"
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


async def test_quiz_attempts_are_stored(client: TestClient, session_factory: async_sessionmaker[AsyncSession]) -> None:
    document_id = await _new_parsed_document(client, session_factory)
    async with session_factory() as session, session.begin():
        parts = await DocumentPartRepository(session).list_by_document(document_id)
        part_id = parts[0].id
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.id == part_id)
            .values(
                status="published",
                content={
                    "quizzes": [{"quiz_key": "q", "type": "single_choice", "correct_answer": 1, "explanation": "yes"}]
                },
            )
        )
    for answer, expected in [(1, True), (2, False)]:
        response = client.post(
            "/api/v1/quiz-attempts", json={"part_id": str(part_id), "quiz_key": "q", "answer": answer}
        )
        assert response.status_code == 200, response.text
        assert response.json()["is_correct"] is expected
    async with session_factory() as session:
        assert (await session.scalars(select(func.count()).select_from(QuizAttempt))).one() == 2


async def test_widget_reports_require_access_and_are_idempotent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    document_id = await _new_parsed_document(client, session_factory)
    async with session_factory() as session, session.begin():
        part = (await DocumentPartRepository(session).list_by_document(document_id))[0]
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="x", compiled_js="x")
        await WidgetUsageRepository(session).add_many(
            part.id,
            [
                WidgetUsageDraft(
                    widget_id=widget.id, directive_ref="slot", position=0, params=None, status=UsageStatus.READY
                )
            ],
        )
    url = f"/api/v1/widgets/{widget.id}/reports"
    body = {"part_id": str(part.id), "reason": "ugly", "comment": "first"}
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json={**body, "comment": "duplicate"}).status_code == 200
    client.cookies.clear()
    _register(client)
    assert client.post(url, json=body).status_code == 404
    async with session_factory() as session:
        records = (await session.scalars(select(Report))).all()
    assert len(records) == 1 and records[0].comment == "first"


async def test_share_material_shows_for_recipient_without_spending_quota(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    email = f"recipient-{uuid4()}@example.com"
    _register(client, email)
    recipient_cookie = client.cookies.get("grasp_session")
    assert recipient_cookie is not None
    client.cookies.clear()
    document_id = await _new_parsed_document(client, session_factory)
    body = {"document_id": str(document_id), "email": email}
    missing = client.post("/api/v1/materials/share", json={**body, "email": "missing@example.com"})
    assert missing.status_code == 422 and missing.json()["error_code"] == "recipient_not_registered"
    assert client.post("/api/v1/materials/share", json=body).status_code == 200
    assert client.post("/api/v1/materials/share", json=body).status_code == 200
    client.cookies.clear()
    client.cookies.set("grasp_session", recipient_cookie)
    listed = client.get("/api/v1/me/materials?filter=shared")
    assert listed.status_code == 200, listed.text
    assert [item["document_id"] for item in listed.json()] == [str(document_id)]
    assert client.post("/api/v1/materials/share", json=body).status_code == 404
    async with session_factory() as session:
        assert (await session.scalars(select(func.count()).select_from(GenerationLedger))).one() == 0


async def test_me_patch_and_quota(client: TestClient, session_factory: async_sessionmaker[AsyncSession]) -> None:
    _register(client)
    before = client.get("/api/v1/me")
    assert before.status_code == 200
    changed = client.patch("/api/v1/me", json={"notify_email": False})
    assert changed.status_code == 200
    assert changed.json() == {**before.json(), "notify_email": False}
    quota = client.get("/api/v1/me/quota")
    assert quota.status_code == 200
    assert quota.json()["monthly_limit"] == 20
    assert quota.json()["available"] == 20
    async with session_factory() as session, session.begin():
        await GenerationLedgerRepository(session).add(
            user_id=UUID(before.json()["id"]),
            op=LedgerOp.RESERVE,
            delta=-4,
            period_start=date.fromisoformat(quota.json()["period_start"]),
        )
    assert client.get("/api/v1/me/quota").json()["available"] == 16


async def test_materials_query_uses_one_statement(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    document_id = await _new_parsed_document(client, session_factory)
    async with session_factory() as session:
        document = await DocumentRepository(session).get(document_id)
        assert document is not None
        queries: list[str] = []

        def count_sql(conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: Any) -> None:
            queries.append(statement)

        engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", count_sql)
        try:
            records = await UserMaterialRepository(session).list_details(document.owner_id, MaterialRole.OWNER)
        finally:
            event.remove(engine, "before_cursor_execute", count_sql)
        assert len(queries) == 1
        assert len(records) == 1 and records[0].parts_total == 3


async def test_import_counts_towards_the_processing_limit(client: TestClient) -> None:
    _register(client)
    first = client.post("/api/v1/documents/import", json={"url": "https://docs.google.com/document/d/first/edit"})
    second = _upload(client, filename="second.pdf")
    assert first.status_code == 201 and second.status_code == 201
    third = client.post("/api/v1/documents/import", json={"url": "https://docs.google.com/document/d/third/edit"})
    assert third.status_code == 429
    assert third.json()["error_code"] == "processing_limit_reached"


async def test_topics_tree_of_a_parsed_document(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _register(client)
    created = _upload(client, filename="lecture.pdf")
    document_id = UUID(created.json()["id"])

    # simulate the finished parse: parsed status, topic tree and parts
    async with session_factory() as session, session.begin():
        documents = DocumentRepository(session)
        await documents.set_status(document_id, DocumentStatus.PARSED)
        await documents.set_topic_tree(
            document_id,
            {
                "topics": [
                    {
                        "id": "topic-adaptive",
                        "title": "Adaptive learning",
                        "children": [{"id": "topic-chunking", "title": "Semantic chunking", "children": []}],
                    }
                ]
            },
        )
        await DocumentPartRepository(session).add_many(
            document_id,
            [
                PartDraft(
                    index=0,
                    title="Part one",
                    topic_ids=["topic-adaptive", "topic-chunking"],
                    source_markdown="part one",
                    token_count=142,
                    profile={},
                ),
                PartDraft(
                    index=1,
                    title="Part two",
                    topic_ids=["topic-chunking"],
                    source_markdown="part two",
                    token_count=178,
                    profile={},
                ),
            ],
        )

    shown = client.get(f"/api/v1/documents/{document_id}/topics")
    assert shown.status_code == 200, shown.text
    topics = shown.json()["topics"]
    assert topics[0]["id"] == "topic-adaptive"
    assert topics[0]["level"] == 1
    assert topics[0]["tokens"] == 320  # 142 + 178, counted once in the subtree
    child = topics[0]["children"][0]
    assert child["id"] == "topic-chunking"
    assert child["level"] == 2
    assert child["tokens"] == 320


async def test_topics_of_a_parsing_document_is_409(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _register(client)
    created = _upload(client)
    document_id = UUID(created.json()["id"])
    async with session_factory() as session, session.begin():
        await DocumentRepository(session).set_status(document_id, DocumentStatus.PARSING)

    shown = client.get(f"/api/v1/documents/{document_id}/topics")
    assert shown.status_code == 409
    body = shown.json()
    assert body["error_code"] == "document_not_ready"
    assert body["status"] == "parsing"


async def test_topics_of_a_failed_document_carries_the_parse_error(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _register(client)
    created = _upload(client)
    document_id = UUID(created.json()["id"])
    async with session_factory() as session, session.begin():
        await DocumentRepository(session).set_status(document_id, DocumentStatus.FAILED, error="parse_failed")

    shown = client.get(f"/api/v1/documents/{document_id}/topics")
    assert shown.status_code == 409
    body = shown.json()
    assert body["error_code"] == "document_not_ready"
    # the client translates the code; the human text stays generic
    assert body["status"] == "failed"
    assert body["reason"] == "parse_failed"


async def test_topics_of_a_foreign_document_is_404(client: TestClient) -> None:
    _register(client, f"owner-{uuid4()}@example.com")
    created = _upload(client)
    client.cookies.clear()
    _register(client, f"stranger-{uuid4()}@example.com")

    shown = client.get(f"/api/v1/documents/{created.json()['id']}/topics")
    assert shown.status_code == 404
    assert shown.json()["error_code"] == "document_not_found"


async def test_plan_preview_is_stable_and_leaves_the_quota_journal_untouched(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _register(client)
    created = _upload(client, filename="lecture.pdf")
    document_id = UUID(created.json()["id"])
    await _make_parsed(document_id, session_factory)

    first = client.post(
        f"/api/v1/documents/{document_id}/plan",
        json={"topic_ids": ["topic-adaptive", "topic-quota"]},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/v1/documents/{document_id}/plan",
        json={"topic_ids": ["topic-adaptive", "topic-quota"]},
    )
    assert second.status_code == 200
    # two consecutive calls with the same topics give the same answer
    assert first.json() == second.json()

    body = first.json()
    assert body["cost"] == len(body["parts"]) == 1
    assert body["parts"][0]["tokens"] == 416  # 142 + 178 + 96
    assert body["available"] == 20  # default monthly limit

    # the journal is untouched: nothing was reserved by the preview
    async with session_factory() as session:
        count = (await session.scalars(select(func.count()).select_from(GenerationLedger))).one()
    assert count == 0


async def _new_parsed_document(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], *, monthly_limit: int = 20
) -> UUID:
    email = f"generation-{uuid4()}@example.com"
    _register(client, email)
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).get_by_email(email)
        assert user is not None
        if monthly_limit != 20:
            from sqlalchemy import update

            from src.app.models.user import User

            await session.execute(update(User).where(User.id == user.id).values(monthly_limit=monthly_limit))
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Test",
            source_type=SourceType.UPLOAD,
            object_key="test.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="d" * 64,
        )
        await UserMaterialRepository(session).create(user_id=user.id, document_id=document.id, role=MaterialRole.OWNER)
    await _make_parsed(document.id, session_factory)
    return document.id


async def test_generate_reserves_creates_parts_and_dispatches(
    client: TestClient, dispatcher: FakeTaskDispatcher, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    document_id = await _new_parsed_document(client, session_factory)
    response = client.post(
        f"/api/v1/documents/{document_id}/generate",
        json={"topic_ids": ["topic-adaptive"], "answers": {"level": "novice", "goal": "exam", "depth": "standard"}},
    )
    assert response.status_code == 202, response.text
    result = response.json()
    assert result["cost"] == 1
    assert result["available"] == 19
    part_id = UUID(result["part_ids"][0])
    assert dispatcher.calls == [("enqueue_part", (part_id, True))]
    async with session_factory() as session:
        part = await DocumentPartRepository(session).get(part_id)
        document = await DocumentRepository(session).get(document_id)
        entries = (await session.scalars(select(GenerationLedger))).all()
    assert part is not None and part.index == 3 and part.source_markdown == "part one\n\npart two"
    assert part.profile == {"level": "novice", "goal": "exam", "depth": "standard"}
    assert document is not None and document.status is DocumentStatus.GENERATING
    assert [(entry.op, entry.delta) for entry in entries] == [("reserve", -1)]


async def test_generate_insufficient_quota_leaves_no_changes(
    client: TestClient, dispatcher: FakeTaskDispatcher, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    document_id = await _new_parsed_document(client, session_factory, monthly_limit=0)
    response = client.post(
        f"/api/v1/documents/{document_id}/generate",
        json={"topic_ids": ["topic-adaptive"], "answers": {"level": "novice", "goal": "exam", "depth": "standard"}},
    )
    assert response.status_code == 402, response.text
    assert response.json()["error_code"] == "quota_exceeded"
    async with session_factory() as session:
        parts = await DocumentPartRepository(session).list_by_document(document_id)
        document = await DocumentRepository(session).get(document_id)
        entries = (await session.scalars(select(GenerationLedger))).all()
    assert len(parts) == 3
    assert document is not None and document.status is DocumentStatus.PARSED
    assert entries == []
    assert dispatcher.calls == []


async def test_plan_rejects_empty_and_unknown_selections(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _register(client)
    created = _upload(client)
    document_id = UUID(created.json()["id"])
    await _make_parsed(document_id, session_factory)

    empty = client.post(f"/api/v1/documents/{document_id}/plan", json={"topic_ids": []})
    assert empty.status_code == 422
    assert empty.json()["error_code"] == "empty_topic_selection"

    unknown = client.post(f"/api/v1/documents/{document_id}/plan", json={"topic_ids": ["nope"]})
    assert unknown.status_code == 422
    assert unknown.json()["error_code"] == "unknown_topic"


async def test_plan_of_a_parsing_document_is_409(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _register(client)
    created = _upload(client)
    document_id = UUID(created.json()["id"])
    async with session_factory() as session, session.begin():
        await DocumentRepository(session).set_status(document_id, DocumentStatus.PARSING)

    response = client.post(f"/api/v1/documents/{document_id}/plan", json={"topic_ids": ["a"]})
    assert response.status_code == 409
    assert response.json()["error_code"] == "document_not_ready"
    assert response.json()["status"] == "parsing"


async def test_shared_user_cannot_plan(client: TestClient, session_factory: async_sessionmaker[AsyncSession]) -> None:
    _register(client, f"owner-{uuid4()}@example.com")
    created = _upload(client)
    document_id = UUID(created.json()["id"])
    await _make_parsed(document_id, session_factory)

    client.cookies.clear()
    _register(client, f"stranger-{uuid4()}@example.com")
    response = client.post(f"/api/v1/documents/{document_id}/plan", json={"topic_ids": ["topic-adaptive"]})
    assert response.status_code == 404
    assert response.json()["error_code"] == "document_not_found"


async def _make_parsed(document_id: UUID, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Simulate a finished parse: parsed status, tree and parts (dev seed shape)."""
    async with session_factory() as session, session.begin():
        documents = DocumentRepository(session)
        await documents.set_status(document_id, DocumentStatus.PARSED)
        await documents.set_topic_tree(
            document_id,
            {
                "topics": [
                    {
                        "id": "topic-adaptive",
                        "title": "Adaptive learning",
                        "children": [
                            {"id": "topic-chunking", "title": "Semantic chunking", "children": []},
                            {"id": "topic-tree", "title": "Topic tree", "children": []},
                        ],
                    },
                    {"id": "topic-quota", "title": "Quota and generation pipeline", "children": []},
                ]
            },
        )
        await DocumentPartRepository(session).add_many(
            document_id,
            [
                PartDraft(
                    index=0,
                    title="What adaptive learning is",
                    topic_ids=["topic-adaptive", "topic-chunking"],
                    source_markdown="part one",
                    token_count=142,
                    profile={},
                ),
                PartDraft(
                    index=1,
                    title="Topic tree and semantic chunks",
                    topic_ids=["topic-chunking", "topic-tree"],
                    source_markdown="part two",
                    token_count=178,
                    profile={},
                ),
                PartDraft(
                    index=2,
                    title="Quota and generation pipeline",
                    topic_ids=["topic-quota"],
                    source_markdown="part three",
                    token_count=96,
                    profile={},
                ),
            ],
        )


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
