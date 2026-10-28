"""Integration test 1.2.3: pgvector column, HNSW index and asyncpg codec."""

import math
import random
from uuid import UUID

import pytest
from sqlalchemy import select, text

from src.app.contracts.widgets import WidgetKind
from src.app.models.widget_description import EMBEDDING_DIM, WidgetDescription
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
from src.app.repositories.widget_repository import WidgetRepository
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration

N_VECTORS = 200
VectorFixture = tuple[UUID, list[list[float]]]


def _random_unit_vector(rng: random.Random) -> list[float]:
    vec = [rng.gauss(0.0, 1.0) for _ in range(EMBEDDING_DIM)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


@pytest.fixture
async def code_widget_with_vectors(session_factory: SessionFactory) -> VectorFixture:
    """A code-kind widget with 200 random descriptions committed to the DB."""
    rng = random.Random(42)
    vectors = [_random_unit_vector(rng) for _ in range(N_VECTORS)]

    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(
            kind=WidgetKind.CODE,
            source_tsx="export default function Demo() {}",
            compiled_js="export {};",
        )
        repository = WidgetDescriptionRepository(session)
        for index, vector in enumerate(vectors):
            await repository.create(
                widget_id=widget.id,
                text=f"description {index}",
                is_paraphrase=False,
                embedding=vector,
            )
    return widget.id, vectors


async def test_asyncpg_roundtrips_list_of_floats(
    session_factory: SessionFactory, code_widget_with_vectors: VectorFixture
) -> None:
    """Vector columns are read back as plain list[float] (no manual codec)."""
    widget_id, _ = code_widget_with_vectors
    async with session_factory() as session:
        rows = await WidgetDescriptionRepository(session).list_by_widget(widget_id)
    assert len(rows) == N_VECTORS
    for row in rows:
        assert isinstance(row.embedding, list)
        assert len(row.embedding) == EMBEDDING_DIM


async def test_nearest_neighbor_found(session_factory: SessionFactory, code_widget_with_vectors: VectorFixture) -> None:
    """The nearest neighbor of one of the inserted vectors is that vector itself."""
    widget_id, vectors = code_widget_with_vectors
    target = vectors[0]
    async with session_factory() as session:
        stmt = (
            select(WidgetDescription)
            .where(WidgetDescription.widget_id == widget_id)
            .order_by(WidgetDescription.embedding.cosine_distance(target))
            .limit(1)
        )
        best = await session.scalar(stmt)
    assert best is not None
    assert best.text == "description 0"


async def test_explain_uses_hnsw_index(
    session_factory: SessionFactory, code_widget_with_vectors: VectorFixture
) -> None:
    """EXPLAIN of ORDER BY embedding <=> :q LIMIT 5 must use the HNSW index."""
    _, vectors = code_widget_with_vectors
    target = _vector_literal(vectors[0])
    query = f"EXPLAIN SELECT id FROM widget_descriptions ORDER BY embedding <=> '{target}'::vector LIMIT 5"
    async with session_factory() as session:
        plan_rows = (await session.execute(text(query))).scalars().all()
    plan = "\n".join(plan_rows)
    assert "ix_widget_descriptions_embedding_hnsw" in plan
    assert "Index Scan" in plan
