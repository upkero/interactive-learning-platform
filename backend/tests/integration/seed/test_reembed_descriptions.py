"""The re-embedding command uses the runtime normalization and updates atomically."""

from collections.abc import Sequence
from threading import Event, Lock
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
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
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
    cache = FakeRedis()
    monkeypatch.setattr(ApplicationContainer, "embeddings_settings", settings)
    monkeypatch.setattr(ApplicationContainer, "embeddings_redis", cache)
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

        # A fresh runtime container must reuse the same model-scoped cache.
        fresh_container = ApplicationContainer()
        try:
            cached = await fresh_container.embedding_service.embed(["first line"])
        finally:
            await fresh_container.close()
        assert cached == [replacement]
        assert calls == [["first line"], ["second line"], ["second line"]]
        assert len(cache.store) == 2
    finally:
        factory.reset_embedder()

    assert calls == [["first line"], ["second line"], ["second line"]]
    assert capsys.readouterr().out == f"reembed-descriptions: updated 2 rows with {BGE_M3_MODEL}\n"


async def test_readers_see_the_old_vector_set_until_reembed_commits(
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = [1.0, *([0.0] * (EMBEDDING_DIM - 1))]
    replacement = [0.0, 1.0, *([0.0] * (EMBEDDING_DIM - 2))]
    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="", compiled_js="")
        session.add(WidgetDescription(id=UUID(int=1), widget_id=widget.id, text="atomic text", embedding=original))

    class RecordingBge:
        def __init__(self, *, device: str) -> None:
            assert device == "cpu"

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return [replacement for _ in texts]

    update_applied = Event()
    allow_commit = Event()
    set_embedding = WidgetDescriptionRepository.set_embedding

    async def pause_before_commit(
        self: WidgetDescriptionRepository,
        description_id: UUID,
        embedding: list[float],
    ) -> None:
        await set_embedding(self, description_id, embedding)
        update_applied.set()
        await anyio.to_thread.run_sync(allow_commit.wait, 10.0)

    settings = EmbeddingsSettings(provider="bge_m3", device="cpu", batch_size=1)
    monkeypatch.setattr(ApplicationContainer, "embeddings_settings", settings)
    monkeypatch.setattr(ApplicationContainer, "embeddings_redis", FakeRedis())
    monkeypatch.setattr(WidgetDescriptionRepository, "set_embedding", pause_before_commit)
    monkeypatch.setattr(factory, "BgeM3Embedder", RecordingBge)
    factory.reset_embedder()
    results: list[int] = []

    async def run_command() -> None:
        results.append(await anyio.to_thread.run_sync(cli.main, ["reembed-descriptions"]))

    try:
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(run_command)
            assert await anyio.to_thread.run_sync(update_applied.wait, 10.0)
            try:
                assert await _vectors(session_factory) == [original]
            finally:
                allow_commit.set()
    finally:
        factory.reset_embedder()

    assert results == [0]
    assert await _vectors(session_factory) == [replacement]


async def test_concurrent_reembed_commands_are_serialized_and_share_the_cache(
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = [1.0, *([0.0] * (EMBEDDING_DIM - 1))]
    replacement = [0.0, 1.0, *([0.0] * (EMBEDDING_DIM - 2))]
    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="", compiled_js="")
        session.add(WidgetDescription(id=UUID(int=1), widget_id=widget.id, text="shared text", embedding=original))

    calls = 0
    active_calls = 0
    max_active_calls = 0
    second_call_started = Event()
    state_lock = Lock()

    class RecordingBge:
        def __init__(self, *, device: str) -> None:
            assert device == "cpu"

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            nonlocal calls, active_calls, max_active_calls
            with state_lock:
                calls += 1
                call_number = calls
                active_calls += 1
                max_active_calls = max(max_active_calls, active_calls)
                if call_number == 2:
                    second_call_started.set()
            try:
                if call_number == 1:
                    # Without the table lock a second command reaches the
                    # provider concurrently and releases this wait.
                    second_call_started.wait(timeout=1.0)
                return [replacement for _ in texts]
            finally:
                with state_lock:
                    active_calls -= 1

    settings = EmbeddingsSettings(provider="bge_m3", device="cpu", batch_size=1)
    cache = FakeRedis()
    monkeypatch.setattr(ApplicationContainer, "embeddings_settings", settings)
    monkeypatch.setattr(ApplicationContainer, "embeddings_redis", cache)
    monkeypatch.setattr(factory, "BgeM3Embedder", RecordingBge)
    factory.reset_embedder()
    results: list[int] = []

    async def run_command() -> None:
        results.append(await anyio.to_thread.run_sync(cli.main, ["reembed-descriptions"]))

    try:
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(run_command)
            task_group.start_soon(run_command)
    finally:
        factory.reset_embedder()

    assert results == [0, 0]
    assert calls == 1
    assert max_active_calls == 1
    assert len(cache.store) == 1
    assert await _vectors(session_factory) == [replacement]
