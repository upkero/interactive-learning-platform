from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bootstrap.container import ApplicationContainer
from src.app.interfaces.llm.llm_client import LLMClient


def get_container(request: Request) -> ApplicationContainer:
    """Extract the DI container from the FastAPI application state."""
    container: ApplicationContainer = request.app.state.container
    return container


ContainerDep = Annotated[ApplicationContainer, Depends(get_container)]


def get_llm_client(container: ContainerDep) -> LLMClient:
    return container.llm_client


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]


async def get_db_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    """Database session generator for API endpoints."""
    async with container.session_factory() as session:
        yield session


DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
