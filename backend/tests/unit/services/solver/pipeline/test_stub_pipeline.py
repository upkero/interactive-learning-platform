import json
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import PartStatus
from src.app.contracts.quota import LedgerOp
from src.app.services.solver.pipeline import stub_pipeline as stub_pipeline_module
from src.app.services.solver.pipeline.stub_pipeline import StubPipeline
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fixtures.solver import build_recovery

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_stub_publishes_once_and_duplicate_delivery_is_noop() -> None:
    case = await build_recovery(PartStatus.QUEUED, 0)
    part = case.part
    session = FakeSession()
    notifier = FakeProgressNotifier()
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: session),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=notifier,
        delay=0,
    )
    await pipeline.process(part.id)
    await pipeline.process(part.id)
    result = await case.parts.get(part.id)
    assert result is not None and result.status is PartStatus.PUBLISHED
    assert result.attempts == 1 and result.content is not None
    assert result.content["schema_version"] == 1
    assert [entry.op for entry in case.ledger.entries] == [LedgerOp.RESERVE, LedgerOp.CHARGE]
    assert [event[1] for event in notifier.events] == ["part_status"] * 4 + ["part_ready", "document_done"]


async def test_invalid_fixture_fails_before_publishing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = tmp_path / "published.json"
    fixture.write_text(json.dumps({"content": {"schema_version": 2}}), encoding="utf-8")
    monkeypatch.setattr(stub_pipeline_module, "PUBLISHED_PART_FIXTURE", fixture)
    case = await build_recovery(PartStatus.QUEUED, 0)
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=case.notifier,
        delay=0,
    )
    with pytest.raises(RuntimeError, match="Invalid published part fixture"):
        await pipeline.process(case.part.id)
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.MAIN_PASS and part.content is None
    assert case.notifier.events == []
