"""Integration test 1.2.6: generation ledger partial unique index."""

from datetime import date
from uuid import UUID

import pytest

from src.app.contracts.documents.statuses import PartStatus
from src.app.contracts.quota import LedgerOp
from src.app.exceptions.quota import QuotaIntegrityError
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration

TODAY = date.today()


async def test_second_refund_for_same_part_fails(
    session_factory: SessionFactory, part_ids: tuple[UUID, UUID, UUID]
) -> None:
    """The partial unique (part_id, op) index blocks a duplicate refund."""
    user_id, _, part_id = part_ids
    async with session_factory() as session, session.begin():
        await DocumentPartRepository(session).transition(
            part_id, expected=frozenset({PartStatus.QUEUED}), to=PartStatus.MAIN_PASS
        )
        repository = GenerationLedgerRepository(session)
        await repository.add(user_id=user_id, op=LedgerOp.REFUND, delta=1, period_start=TODAY, part_id=part_id)
        with pytest.raises(QuotaIntegrityError):
            await repository.add(user_id=user_id, op=LedgerOp.REFUND, delta=1, period_start=TODAY, part_id=part_id)


async def test_two_charges_for_same_part_fail(
    session_factory: SessionFactory, part_ids: tuple[UUID, UUID, UUID]
) -> None:
    """Two charges for the same part are blocked by the partial index too."""
    user_id, _, part_id = part_ids
    async with session_factory() as session, session.begin():
        await DocumentPartRepository(session).transition(
            part_id, expected=frozenset({PartStatus.QUEUED}), to=PartStatus.MAIN_PASS
        )
        repository = GenerationLedgerRepository(session)
        await repository.add(user_id=user_id, op=LedgerOp.CHARGE, delta=0, period_start=TODAY, part_id=part_id)
        with pytest.raises(QuotaIntegrityError):
            await repository.add(user_id=user_id, op=LedgerOp.CHARGE, delta=0, period_start=TODAY, part_id=part_id)


async def test_reserve_without_part_id_is_unlimited(
    session_factory: SessionFactory, part_ids: tuple[UUID, UUID, UUID]
) -> None:
    """Reserves without a part are not constrained by the partial index."""
    user_id, _, _ = part_ids
    async with session_factory() as session, session.begin():
        repository = GenerationLedgerRepository(session)
        for _ in range(3):
            entry = await repository.add(user_id=user_id, op=LedgerOp.RESERVE, delta=-1, period_start=TODAY)
            assert entry.part_id is None
        assert await repository.sum_delta(user_id, TODAY) == -3
