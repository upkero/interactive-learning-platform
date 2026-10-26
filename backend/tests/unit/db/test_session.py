import pytest
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from src.app.db.session import build_engine

pytestmark = pytest.mark.unit


def test_build_engine_with_null_pool() -> None:
    """Проверяет, что при null_pool=True создается NullPool."""
    engine = build_engine("postgresql+asyncpg://grasp:pass@localhost:5432/grasp", null_pool=True)
    assert isinstance(engine.pool, NullPool)


def test_build_engine_default_pool() -> None:
    """Проверяет, что по умолчанию создается стандартный пул соединений."""
    engine = build_engine("postgresql+asyncpg://grasp:pass@localhost:5432/grasp", null_pool=False)
    assert isinstance(engine.pool, AsyncAdaptedQueuePool)
