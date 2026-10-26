from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def build_engine(
    url: str,
    *,
    pool_size: int = 10,
    max_overflow: int = 5,
    null_pool: bool = False,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine with NullPool and pre-ping support."""
    if null_pool:
        return create_async_engine(
            url,
            poolclass=NullPool,
            pool_pre_ping=True,
        )

    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory with expire_on_commit=False."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
