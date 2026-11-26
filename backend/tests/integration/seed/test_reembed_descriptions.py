"""The re-embedding command uses the runtime normalization and updates atomically."""

from collections.abc import Sequence
from uuid import UUID

import anyio.to_thread
import pytest
from sqlalchemy import select

from src import cli
from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.widgets import WidgetKind
from src.app.core.settings.embeddings import EmbeddingsSettings
from src.app.embeddings import factory
from src.app.embeddings.bge_m3 import BGE_M3_MODEL
from src.app.exceptions.embeddings import EmbeddingGenerationError
from src.app.models.widget_description import EMBEDDING_DIM, WidgetDescription
from src.app.repositories.widget_repository import WidgetRepository
from tests.support.fakes.cache.redis import FakeRedis
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


async def _vectors(session_factory: SessionFactory) -> list[list[float]]:
    async with session_factory() as session:
        rows = await session.scalars(select(WidgetDescription.embedding).order_by(WidgetDescription.id))
        return [list(vector) for vector in rows]


async def test_failed_late_batch_rolls_back_and_retry_normalizes_all_rows(
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = [1.0, *([0.0] * (EMBEDDING_DIM - 1))]
    replacement = [0.0, 1.0, *([0.0] * (EMBEDDING_DIM - 2))]
    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="", compiled_js="")
        session.add_all(
            [
                WidgetDescription(id=UUID(int=1), widget_id=widget.id, text="  first\nline ", embedding=original),
                WidgetDescription(id=UUID(int=2), widget_id=widget.id, text="  second\tline ", embedding=original),
            ]
        )

    calls: list[list[str]] = []
    should_fail = True

    class RecordingBge:
        def __init__(self, *, device: str) -> None:
            assert device == "cpu"

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            calls.append(list(texts))
            if should_fail and texts == ["second line"]:
                raise RuntimeError("provider failed on second page")
            return [replacement for _ in texts]

    settings = EmbeddingsSettings(provider="bge_m3", device="cpu", batch_size=1)
    monkeypatch.setattr(ApplicationContainer, "embeddings_settings", settings)
    monkeypatch.setattr(ApplicationContainer, "embeddings_redis", FakeRedis())
    monkeypatch.setattr(factory, "BgeM3Embedder", RecordingBge)
    factory.reset_embedder()
    try:
        with pytest.raises(EmbeddingGenerationError) as error:
            await anyio.to_thread.run_sync(cli.main, ["reembed-descriptions"])
        assert isinstance(error.value.__cause__, RuntimeError)
        assert await _vectors(session_factory) == [original, original]

        should_fail = False
        assert await anyio.to_thread.run_sync(cli.main, ["reembed-descriptions"]) == 0
        assert await _vectors(session_factory) == [replacement, replacement]
    finally:
        factory.reset_embedder()

    assert calls == [["first line"], ["second line"], ["second line"]]
    assert capsys.readouterr().out == f"reembed-descriptions: updated 2 rows with {BGE_M3_MODEL}\n"
