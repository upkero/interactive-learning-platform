"""Integration test 1.2.5: widget kind CHECK and report uniqueness."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.app.contracts.widgets import ReportReason, WidgetKind
from src.app.exceptions.widgets import WidgetConstraintError
from src.app.models.widget import Widget
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


async def test_config_widget_without_primitive_fails(session_factory: SessionFactory) -> None:
    """A config widget without primitive_id must hit the kind-fields CHECK."""
    async with session_factory() as session, session.begin():
        repository = WidgetRepository(session)
        with pytest.raises(WidgetConstraintError):
            await repository.create(kind=WidgetKind.CONFIG, mode="m", params={"a": 1})


async def test_config_widget_without_mode_fails(session_factory: SessionFactory) -> None:
    """A config widget without mode must hit the kind-fields CHECK."""
    async with session_factory() as session, session.begin():
        repository = WidgetRepository(session)
        with pytest.raises(WidgetConstraintError):
            await repository.create(kind=WidgetKind.CONFIG, primitive_id="p", params={"a": 1})


async def test_config_widget_without_params_fails(session_factory: SessionFactory) -> None:
    """A config widget with params=None (SQL NULL) must hit the kind-fields CHECK.

    This only holds when JSONB binds Python None as SQL NULL
    (``none_as_null``): JSON ``null`` would satisfy ``params IS NOT NULL``.
    """
    async with session_factory() as session, session.begin():
        repository = WidgetRepository(session)
        with pytest.raises(WidgetConstraintError):
            await repository.create(kind=WidgetKind.CONFIG, primitive_id="p", mode="m", params=None)


async def test_code_widget_params_is_sql_null(session_factory: SessionFactory) -> None:
    """A code widget stores params as SQL NULL, not JSON ``null``."""
    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="t", compiled_js="j")
        params_type = await session.scalar(select(func.jsonb_typeof(Widget.params)).where(Widget.id == widget.id))
    # jsonb_typeof returns NULL for a SQL NULL argument.
    assert params_type is None


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
