"""Reservation-period backfill on an existing database."""

import asyncio
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import PartDraft, SourceType
from src.app.contracts.quota import LedgerOp
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository

pytestmark = pytest.mark.integration
BACKEND_DIR = Path(__file__).resolve().parents[3]


async def test_part_quota_migration_backfills_latest_reservation_and_keeps_unreserved_null(
    session_factory: async_sessionmaker[AsyncSession], part_ids: tuple[UUID, UUID, UUID]
) -> None:
    user_id, document_id, part_id = part_ids
    async with session_factory() as session, session.begin():
        ledger = GenerationLedgerRepository(session)
        for period in (date(2026, 10, 1), date(2026, 11, 1)):
            await ledger.add(
                user_id=user_id, document_id=document_id, op=LedgerOp.RESERVE, delta=-1, period_start=period
            )
        document = await DocumentRepository(session).create(
            owner_id=user_id,
            title="Unreserved",
            source_type=SourceType.UPLOAD,
            object_key="seed.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="d" * 64,
        )
        (unreserved,) = await DocumentPartRepository(session).add_many(
            document.id,
            [
                PartDraft(
                    index=0, title="Seed", topic_ids=[], source_markdown="x", token_count=1, quota_period_start=None
                )
            ],
        )
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    try:
        await asyncio.to_thread(command.downgrade, config, "0003_document_error_code")
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
    async with session_factory() as session:
        parts = DocumentPartRepository(session)
        owner = await parts.part_owner(part_id)
        assert owner is not None and owner.quota_period_start == date(2026, 11, 1)
        owner = await parts.part_owner(unreserved.id)
        assert owner is not None and owner.quota_period_start is None
