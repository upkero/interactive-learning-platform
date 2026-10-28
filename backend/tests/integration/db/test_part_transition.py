"""Integration test 1.2.7: atomic compare-and-set transition of part status."""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select

from src.app.contracts.documents.statuses import PartStatus
from src.app.models.document_part import DocumentPart
from src.app.repositories.document_part_repository import DocumentPartRepository
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


async def test_transition_updates_stage_changed_at(
    session_factory: SessionFactory, part_ids: tuple[UUID, UUID, UUID]
) -> None:
    """A successful transition must refresh stage_changed_at (watchdog anchor)."""
    _, _, part_id = part_ids
    async with session_factory() as session, session.begin():
        repository = DocumentPartRepository(session)
        before = await repository.get(part_id)
        assert before is not None
        ok = await repository.transition(
            part_id, expected=frozenset({PartStatus.QUEUED}), to=PartStatus.MAIN_PASS, bump_attempts=True
        )
        assert ok is True
        after = await repository.get(part_id)
        assert after is not None
        assert after.status is PartStatus.MAIN_PASS
        assert after.attempts == before.attempts + 1
        assert after.stage_changed_at > before.stage_changed_at


async def test_transition_sets_published_at(session_factory: SessionFactory, part_ids: tuple[UUID, UUID, UUID]) -> None:
    """Transitioning to ``published`` must stamp published_at."""
    _, _, part_id = part_ids
    async with session_factory() as session, session.begin():
        repository = DocumentPartRepository(session)
        ok = await repository.transition(part_id, expected=frozenset({PartStatus.QUEUED}), to=PartStatus.PUBLISHED)
        assert ok is True
        published = await repository.get(part_id)
        assert published is not None
        assert published.published_at is not None


async def test_transition_from_unexpected_status_is_rejected(
    session_factory: SessionFactory, part_ids: tuple[UUID, UUID, UUID]
) -> None:
    """The compare-and-set UPDATE refuses statuses outside ``expected``."""
    _, _, part_id = part_ids
    async with session_factory() as session, session.begin():
        repository = DocumentPartRepository(session)
        ok = await repository.transition(part_id, expected=frozenset({PartStatus.PUBLISHED}), to=PartStatus.FAILED)
        assert ok is False


async def test_two_parallel_transitions_exactly_one_wins(
    session_factory: SessionFactory, part_ids: tuple[UUID, UUID, UUID]
) -> None:
    """Two concurrent transitions of one part: exactly one True, one False."""
    _, _, part_id = part_ids

    async def attempt(to: PartStatus) -> bool:
        async with session_factory() as session, session.begin():
            repository = DocumentPartRepository(session)
            return await repository.transition(part_id, expected=frozenset({PartStatus.QUEUED}), to=to)

    results = await asyncio.gather(attempt(PartStatus.MAIN_PASS), attempt(PartStatus.MAIN_PASS))
    assert sorted(results) == [False, True]

    async with session_factory() as session:
        status = await session.scalar(select(DocumentPart.status).where(DocumentPart.id == part_id))
    assert status == PartStatus.MAIN_PASS.value
