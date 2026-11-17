"""Shared resources for quota integration tests."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from src.app.services.solver.pipeline.watchdog import Watchdog
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher


@pytest.fixture
async def container() -> AsyncIterator[ApplicationContainer]:
    instance = ApplicationContainer()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
def dispatcher() -> FakeTaskDispatcher:
    return FakeTaskDispatcher()


@pytest.fixture
def recovery(
    session_factory: async_sessionmaker[AsyncSession], container: ApplicationContainer, dispatcher: FakeTaskDispatcher
) -> PartRecovery:
    return PartRecovery(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=container.quota_ledger,
        dispatcher=dispatcher,
        notifier=FakeProgressNotifier(),
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
