"""DI container dependency."""

from typing import Annotated

from fastapi import Depends, Request

from src.app.bootstrap.container import ApplicationContainer


def get_container(request: Request) -> ApplicationContainer:
    """Extract the DI container from the FastAPI application state."""
    container: ApplicationContainer = request.app.state.container
    return container


ContainerDep = Annotated[ApplicationContainer, Depends(get_container)]
