"""Integration tests 1.2.7: every repository against real Postgres."""

import dataclasses
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import DocumentStatus, MaterialRole, SourceType
from src.app.contracts.quizzes import QuizAttemptRecord
from src.app.contracts.quota import LedgerOp
from src.app.contracts.users import UserRecord
from src.app.contracts.widgets import (
    ReportReason,
    UsageStatus,
    WidgetKind,
    WidgetStatus,
    WidgetUsageDraft,
)
from src.app.exceptions.users import UserAlreadyExistsError
from src.app.models.document_part import DocumentPart
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.primitive_repository import PrimitiveRepository
from src.app.repositories.quiz_attempt_repository import QuizAttemptRepository
from src.app.repositories.report_repository import ReportRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


async def _new_document(
    session_factory: SessionFactory, *, source_type: SourceType = SourceType.UPLOAD
) -> tuple[UUID, UUID]:
    """Committed user + document pair; returns (user_id, document_id)."""
    email = f"u-{uuid4()}@grasp.test"
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=email, password_hash="hash")
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Doc",
            source_type=source_type,
            object_key=f"docs/{email}",
            mime_type="text/markdown",
            size_bytes=10,
            checksum="c" * 64,
        )
    return user.id, document.id


async def _create_part(session: AsyncSession, document_id: UUID) -> PartRecord:
    """Add one queued part inside the caller's transaction."""
    repository = DocumentPartRepository(session)
    (part,) = await repository.add_many(
        document_id,
        [PartDraft(index=0, title="P", topic_ids=[], source_markdown="m", token_count=1)],
    )
    return part


async def test_user_repository_roundtrip(session_factory: SessionFactory) -> None:
    """CITEXT folds the case: get_by_email finds the user in any casing."""
    email = f"u-{uuid4()}@grasp.test"
    async with session_factory() as session, session.begin():
        repository = UserRepository(session)
        created = await repository.create(email=email.upper(), password_hash="h", display_name="N")
        # Before commit the identity map still holds the value we passed:
        # CITEXT folding happens on the database side, not in Python.
        assert created.email == email.upper()
        fetched = await repository.get(created.id)
        by_email = await repository.get_by_email(email.upper())
        assert fetched == created
        assert by_email == created
    # A fresh session reads straight from the database. asyncpg encodes
    # unknown-to-it types (citext) in binary format, and citext folds case
    # only in its input function - so the stored value keeps the original
    # case, while comparisons (and the unique index) stay case-insensitive.
    # The lookup with a differently-cased email proves the folding.
    async with session_factory() as session:
        folded = await UserRepository(session).get_by_email(email)
    assert folded is not None
    assert folded.id == created.id
    assert folded.email.lower() == email


async def test_duplicate_email_raises_domain_exception(session_factory: SessionFactory) -> None:
    """The CITEXT uniqueness surfaces as UserAlreadyExistsError."""
    email = f"u-{uuid4()}@grasp.test"
    async with session_factory() as session, session.begin():
        repository = UserRepository(session)
        await repository.create(email=email, password_hash="hash")
        with pytest.raises(UserAlreadyExistsError):
            await repository.create(email=email.upper(), password_hash="hash")


async def test_contract_is_immutable(session_factory: SessionFactory) -> None:
    """Contracts are frozen: mutation attempts raise FrozenInstanceError."""
    email = f"u-{uuid4()}@grasp.test"
    async with session_factory() as session, session.begin():
        created: UserRecord = await UserRepository(session).create(email=email, password_hash="hash")
    with pytest.raises(dataclasses.FrozenInstanceError):
        created.email = "other@grasp.test"  # type: ignore[misc]


async def test_document_repository_roundtrip(session_factory: SessionFactory) -> None:
    user_id, document_id = await _new_document(session_factory)
    async with session_factory() as session, session.begin():
        repository = DocumentRepository(session)
        owned = await repository.get_owned(document_id, user_id)
        assert owned is not None and owned.status is DocumentStatus.UPLOADED
        assert await repository.get_owned(document_id, uuid4()) is None

        parsed = await repository.set_status(document_id, DocumentStatus.PARSED)
        assert parsed is not None and parsed.status is DocumentStatus.PARSED

        with_tree = await repository.set_topic_tree(
            document_id, {"topics": [{"id": "t1", "title": "T", "children": []}]}
        )
        assert with_tree is not None and with_tree.topic_tree is not None

        # uploaded and parsed both count as active; done does not
        assert await repository.count_active(user_id) == 1
        await repository.set_status(document_id, DocumentStatus.DONE)
        assert await repository.count_active(user_id) == 0


async def test_document_part_repository_roundtrip(session_factory: SessionFactory) -> None:
    _, document_id = await _new_document(session_factory)
    async with session_factory() as session, session.begin():
        repository = DocumentPartRepository(session)
        created = await repository.add_many(
            document_id,
            [
                PartDraft(index=1, title="B", topic_ids=["t"], source_markdown="b", token_count=2),
                PartDraft(index=0, title="A", topic_ids=[], source_markdown="a", token_count=1),
            ],
        )
        listed = await repository.list_by_document(document_id)
        # Unpublished parts must store SQL NULL, not JSON "null", so that
        # `content IS NULL` queries (watchdog, publishing) work correctly.
        content_type = await session.scalar(
            select(func.jsonb_typeof(DocumentPart.content)).where(DocumentPart.id == created[1].id)
        )
    assert [p.index for p in listed] == [0, 1]
    assert created[0].topic_ids == ("t",)
    assert listed[0].id == created[1].id
    assert content_type is None


async def test_image_repository_roundtrip(session_factory: SessionFactory) -> None:
    _, document_id = await _new_document(session_factory)
    async with session_factory() as session, session.begin():
        repository = ImageRepository(session)
        (created,) = await repository.add_many(
            document_id,
            [ImageDraft(object_key="img/1.png", width=10, height=20, page=1)],
        )
        assert await repository.get(created.id) == created
        assert [i.id for i in await repository.list_by_document(document_id)] == [created.id]


async def test_user_material_repository_roundtrip(session_factory: SessionFactory) -> None:
    owner_id, document_id = await _new_document(session_factory)
    async with session_factory() as session, session.begin():
        other_user = await UserRepository(session).create(email=f"u-{uuid4()}@grasp.test", password_hash="hash")
        repository = UserMaterialRepository(session)
        await repository.create(user_id=owner_id, document_id=document_id, role=MaterialRole.OWNER)
        assert await repository.get_role(owner_id, document_id) is MaterialRole.OWNER
        shared = await repository.create(
            user_id=other_user.id, document_id=document_id, role=MaterialRole.SHARED, shared_by=owner_id
        )
        assert shared.shared_by == owner_id
        assert len(await repository.list_by_user(owner_id)) == 1


async def test_primitive_repository_upsert(session_factory: SessionFactory) -> None:
    async with session_factory() as session, session.begin():
        repository = PrimitiveRepository(session)
        created = await repository.upsert(
            primitive_id="p-1", version="0.1.0", description="d", modes=["single"], params_schema={"type": "object"}
        )
        updated = await repository.upsert(
            primitive_id="p-1", version="0.2.0", description="d2", modes=["single", "multiple"], params_schema={}
        )
        listed = await repository.list_all()
        fetched = await repository.get("p-1")
    assert created.version == "0.1.0"
    assert updated.version == "0.2.0"
    assert fetched == updated
    assert [p.id for p in listed] == ["p-1"]


async def test_widget_repository_roundtrip(session_factory: SessionFactory) -> None:
    async with session_factory() as session, session.begin():
        repository = WidgetRepository(session)
        code = await repository.create(kind=WidgetKind.CODE, source_tsx="t", compiled_js="j")
        fetched = await repository.get(code.id)
        await repository.set_status(code.id, WidgetStatus.EXCLUDED)
        excluded = await repository.get(code.id)
    assert fetched == code
    assert excluded is not None and excluded.status is WidgetStatus.EXCLUDED


async def test_widget_description_repository_roundtrip(session_factory: SessionFactory) -> None:
    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="t", compiled_js="j")
        repository = WidgetDescriptionRepository(session)
        created = await repository.create(widget_id=widget.id, text="t", is_paraphrase=False, embedding=[0.0] * 1024)
        listed = await repository.list_by_widget(widget.id)
    assert listed == [created]


async def test_widget_usage_repository_roundtrip(session_factory: SessionFactory) -> None:
    _, document_id = await _new_document(session_factory)
    async with session_factory() as session, session.begin():
        part = await _create_part(session, document_id)
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="t", compiled_js="j")
        repository = WidgetUsageRepository(session)
        (created,) = await repository.add_many(
            part.id,
            [WidgetUsageDraft(directive_ref="d1", position=0, widget_id=widget.id, status=UsageStatus.READY)],
        )
        fetched = await repository.get(created.id)
        await repository.set_status(created.id, UsageStatus.PENDING)
        updated = await repository.get(created.id)
    assert fetched is not None and fetched.widget_id == widget.id
    assert updated is not None and updated.status is UsageStatus.PENDING


async def test_report_repository_roundtrip(session_factory: SessionFactory) -> None:
    user_id, _ = await _new_document(session_factory)
    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="t", compiled_js="j")
        repository = ReportRepository(session)
        created = await repository.create_if_not_exists(widget_id=widget.id, user_id=user_id, reason=ReportReason.WRONG)
        fetched = await repository.get_by_widget_and_user(widget.id, user_id)
    assert created is not None and fetched == created


async def test_quiz_attempt_repository_roundtrip(session_factory: SessionFactory) -> None:
    user_id, document_id = await _new_document(session_factory)
    async with session_factory() as session, session.begin():
        part = await _create_part(session, document_id)
        repository = QuizAttemptRepository(session)
        created = await repository.create(
            user_id=user_id, part_id=part.id, quiz_key="q_1a2b3c4d", answer={"choice": 0}, is_correct=True
        )
        listed = await repository.list_by_part(part.id)
    assert listed == [created]
    assert isinstance(created, QuizAttemptRecord)
    assert created.quiz_key == "q_1a2b3c4d"


async def test_generation_ledger_repository_roundtrip(session_factory: SessionFactory) -> None:
    user_id, document_id = await _new_document(session_factory)
    period_start = date(2026, 1, 1)
    async with session_factory() as session, session.begin():
        part = await _create_part(session, document_id)
        repository = GenerationLedgerRepository(session)
        reserve = await repository.add(
            user_id=user_id,
            op=LedgerOp.RESERVE,
            delta=-2,
            period_start=period_start,
            document_id=document_id,
            part_id=part.id,
        )
        total = await repository.sum_delta(user_id, period_start)
    assert reserve.delta == -2
    assert total == -2
