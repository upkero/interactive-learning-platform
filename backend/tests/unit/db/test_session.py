import pytest
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from src.app.db.session import build_engine

pytestmark = pytest.mark.unit


def test_build_engine_with_null_pool() -> None:
    """null_pool=True produces a NullPool engine."""
    engine = build_engine("postgresql+asyncpg://grasp:pass@localhost:5432/grasp", null_pool=True)
    assert isinstance(engine.pool, NullPool)


def test_build_engine_default_pool() -> None:
    """By default a standard connection pool is created."""
    engine = build_engine("postgresql+asyncpg://grasp:pass@localhost:5432/grasp", null_pool=False)
    assert isinstance(engine.pool, AsyncAdaptedQueuePool)
