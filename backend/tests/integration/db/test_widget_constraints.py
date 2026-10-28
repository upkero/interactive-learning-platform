"""Integration test 1.2.5: widget kind CHECK and report uniqueness."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.app.contracts.widgets import ReportReason, WidgetKind
from src.app.exceptions.widgets import WidgetConstraintError
from src.app.repositories.report_repository import ReportRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_repository import WidgetRepository
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


async def test_code_widget_without_source_tsx_fails(session_factory: SessionFactory) -> None:
    """Inserting a code widget without source_tsx/compiled_js must hit the CHECK."""
    async with session_factory() as session, session.begin():
        repository = WidgetRepository(session)
        with pytest.raises(WidgetConstraintError):
            await repository.create(kind=WidgetKind.CODE)


async def test_config_widget_without_params_fails(session_factory: SessionFactory) -> None:
    """Inserting a config widget without primitive/mode/params must hit the CHECK."""
    async with session_factory() as session, session.begin():
        repository = WidgetRepository(session)
        with pytest.raises(WidgetConstraintError):
            await repository.create(kind=WidgetKind.CONFIG)


async def test_second_report_from_same_user_conflicts(session_factory: SessionFactory) -> None:
    """The (widget_id, user_id) uniqueness blocks a duplicate complaint."""
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email="report@grasp.test", password_hash="hash")
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="x", compiled_js="y")
        repository = ReportRepository(session)
        first = await repository.create_if_not_exists(widget_id=widget.id, user_id=user.id, reason=ReportReason.BROKEN)
        assert first is not None
        second = await repository.create_if_not_exists(widget_id=widget.id, user_id=user.id, reason=ReportReason.BROKEN)
        assert second is None


async def test_raw_duplicate_report_violates_uniqueness(session_factory: SessionFactory) -> None:
    """A direct second insert of the same report raises IntegrityError."""
    from sqlalchemy import insert

    from src.app.models.report import Report

    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email="report2@grasp.test", password_hash="hash")
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="x", compiled_js="y")
        repository = ReportRepository(session)
        await repository.create_if_not_exists(widget_id=widget.id, user_id=user.id, reason=ReportReason.BROKEN)
        stmt = insert(Report).values(widget_id=widget.id, user_id=user.id, reason="broken")
        with pytest.raises(IntegrityError):
            await session.execute(stmt)
