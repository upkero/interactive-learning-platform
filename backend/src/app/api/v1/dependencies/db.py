"""Database session dependency."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.api.v1.dependencies.container import ContainerDep


async def get_db_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    """Database session generator for API endpoints."""
    async with container.session_factory() as session:
        yield session


DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
