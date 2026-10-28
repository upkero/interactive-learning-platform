"""Integration tests: foreign-key violations must not be mis-translated.

Each repository may map only its own constraint to the specific domain
exception; every other ``IntegrityError`` (first of all foreign keys)
must surface as the generic area error, not as a fake "duplicate".
"""

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.widgets import ReportReason, UsageStatus, WidgetKind, WidgetUsageDraft
from src.app.exceptions.documents import DocumentPartDuplicateError, DocumentsIntegrityError
from src.app.exceptions.quizzes import QuizIntegrityError
from src.app.exceptions.widgets import WidgetConstraintError, WidgetsIntegrityError, WidgetUsageDuplicateError
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.quiz_attempt_repository import QuizAttemptRepository
from src.app.repositories.report_repository import ReportRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


async def _real_user(session_factory: SessionFactory) -> UUID:
    """Create a committed user so user_id FKs stay satisfiable."""
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"u-{uuid4()}@grasp.test", password_hash="hash")
    return user.id


async def test_part_fk_for_missing_document_is_generic(
    session_factory: SessionFactory,
) -> None:
    """A part for a nonexistent document is an FK error, not a duplicate."""
    async with session_factory() as session, session.begin():
        with pytest.raises(DocumentsIntegrityError) as exc_info:
            await DocumentPartRepository(session).add_many(
                uuid4(),
                [PartDraft(index=0, title="T", topic_ids=[], source_markdown="m", token_count=1)],
            )
        assert not isinstance(exc_info.value, DocumentPartDuplicateError)


async def test_image_fk_for_missing_document_is_generic(
    session_factory: SessionFactory,
) -> None:
    """Images translate FK violations into the documents area error."""
    async with session_factory() as session, session.begin():
        with pytest.raises(DocumentsIntegrityError):
            await ImageRepository(session).add_many(
                uuid4(),
                [ImageDraft(object_key="img/x.png", width=1, height=1)],
            )


async def test_usage_fk_for_missing_part_is_generic(
    session_factory: SessionFactory,
) -> None:
    """A usage for a nonexistent part is an FK error, not a duplicate."""
    widget_id: UUID | None = None
    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="t", compiled_js="j")
        widget_id = widget.id
        with pytest.raises(WidgetsIntegrityError) as exc_info:
            await WidgetUsageRepository(session).add_many(
                uuid4(),
                [
                    WidgetUsageDraft(
                        directive_ref="d1",
                        position=0,
                        widget_id=widget_id,
                        status=UsageStatus.PENDING,
                    )
                ],
            )
        assert not isinstance(exc_info.value, WidgetUsageDuplicateError)


async def test_widget_fk_for_unknown_primitive_is_generic(
    session_factory: SessionFactory,
) -> None:
    """A config widget with a nonexistent primitive_id is an FK error."""
    async with session_factory() as session, session.begin():
        with pytest.raises(WidgetsIntegrityError) as exc_info:
            await WidgetRepository(session).create(
                kind=WidgetKind.CONFIG,
                primitive_id=f"ghost-{uuid4()}",
                mode="m",
                params={"a": 1},
            )
        assert not isinstance(exc_info.value, WidgetConstraintError)


async def test_report_fk_for_missing_widget_is_generic(
    session_factory: SessionFactory,
) -> None:
    """A report for a nonexistent widget surfaces as the area error."""
    user_id = await _real_user(session_factory)
    async with session_factory() as session, session.begin():
        with pytest.raises(WidgetsIntegrityError):
            await ReportRepository(session).create_if_not_exists(
                widget_id=uuid4(),
                user_id=user_id,
                reason=ReportReason.BROKEN,
            )


async def test_quiz_attempt_fk_for_missing_part_is_generic(
    session_factory: SessionFactory,
) -> None:
    """A quiz attempt for a nonexistent part surfaces as the area error."""
    user_id = await _real_user(session_factory)
    answer: dict[str, Any] = {"choice": 0}
    async with session_factory() as session, session.begin():
        with pytest.raises(QuizIntegrityError):
            await QuizAttemptRepository(session).create(
                user_id=user_id,
                part_id=uuid4(),
                quiz_key="q_deadbeef",
                answer=answer,
                is_correct=True,
            )
