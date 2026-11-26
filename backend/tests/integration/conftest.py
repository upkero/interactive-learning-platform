"""Integration fixtures: real Postgres (pgvector/pgvector:pg17) from compose/CI.

The schema is created once per session with ``alembic upgrade head``
(migration behaviour is part of the acceptance criteria); every test
starts from a truncated database. When no Postgres is reachable the
whole integration suite is skipped, so local unit-only runs stay green.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.statuses import SourceType
from src.app.core.clock import SystemClock
from src.app.core.settings.app import get_app_settings
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.quota.period import current_period
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from src.app.services.solver.pipeline.watchdog import Watchdog
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher

BACKEND_DIR: Path = Path(__file__).resolve().parents[2]

ALL_TABLES: tuple[str, ...] = (
    "users",
    "documents",
    "document_parts",
    "images",
    "user_materials",
    "primitives",
    "widgets",
    "widget_descriptions",
    "widget_usages",
    "reports",
    "quiz_attempts",
    "generation_ledger",
)


def _apply_migrations(target: str) -> None:
    """Run alembic in a fresh event loop (env.py calls asyncio.run itself)."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, target)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[AsyncEngine]:
    """Engine over the test database with the migration applied; NullPool.

    NullPool is essential: connections must not outlive the event loop of
    a single test, so nothing is cached between tests.
    """
    engine = create_async_engine(str(get_app_settings().db_url), poolclass=NullPool, pool_pre_ping=True)
    try:
        asyncio.run(_ping(engine))
    except (OSError, ConnectionRefusedError, TimeoutError) as exc:
        if os.environ.get("CI"):
            # In CI a broken database service must fail the build, not
            # silently turn the whole integration suite into skips.
            pytest.fail(f"Postgres must be reachable in CI: {exc}")
        pytest.skip(f"Postgres is not reachable, skipping integration tests: {exc}")
    _apply_migrations("head")
    yield engine
    asyncio.run(engine.dispose())


async def _ping(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


@pytest.fixture
async def db(db_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    """Truncate every table so each test starts from an empty database."""
    async with db_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(ALL_TABLES)} CASCADE"))
    yield db_engine


@pytest.fixture
def session_factory(db: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db, expire_on_commit=False)


@pytest.fixture
async def container() -> AsyncIterator[ApplicationContainer]:
    instance = ApplicationContainer()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
def ledger(container: ApplicationContainer) -> QuotaLedger:
    return container.quota_ledger


@pytest.fixture
def dispatcher() -> FakeTaskDispatcher:
    return FakeTaskDispatcher()


@pytest.fixture
def recovery(
    session_factory: async_sessionmaker[AsyncSession],
    ledger: QuotaLedger,
    dispatcher: FakeTaskDispatcher,
    container: ApplicationContainer,
) -> PartRecovery:
    return PartRecovery(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=ledger,
        dispatcher=dispatcher,
        notifier=FakeProgressNotifier(),
        users=UserRepository,
        notifications=container.notification_service,
    )


@pytest.fixture
def watchdog(
    session_factory: async_sessionmaker[AsyncSession], recovery: PartRecovery, dispatcher: FakeTaskDispatcher
) -> Watchdog:
    return Watchdog(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        recovery=recovery,
        dispatcher=dispatcher,
        metrics=RecordingMetricsCollector(),
    )


@pytest.fixture
async def part_ids(session_factory: async_sessionmaker[AsyncSession]) -> tuple[UUID, UUID, UUID]:
    """Committed user -> document -> single queued part chain."""
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email="part@grasp.test", password_hash="hash", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Race document",
            source_type=SourceType.UPLOAD,
            object_key="docs/test.md",
            mime_type="text/markdown",
            size_bytes=10,
            checksum="c" * 64,
        )
        (part,) = await DocumentPartRepository(session).add_many(
            document.id,
            [
                PartDraft(
                    index=0,
                    title="Part",
                    topic_ids=[],
                    source_markdown="# part",
                    token_count=1,
                    quota_period_start=current_period(SystemClock().today(), None).start,
                )
            ],
        )
    return user.id, document.id, part.id
