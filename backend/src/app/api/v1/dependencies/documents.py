"""Document-related dependencies."""

from typing import Annotated

from fastapi import Depends

from src.app.api.v1.dependencies.container import ContainerDep
from src.app.api.v1.dependencies.db import DBSessionDep
from src.app.repositories.image_repository import ImageRepository
from src.app.services.documents.image_url_resolver import ImageUrlResolver


def get_image_url_resolver(container: ContainerDep, session: DBSessionDep) -> ImageUrlResolver:
    """Per-request resolver: repository bound to the request session.

    Wired here (not in the container) because the repository is session-
    scoped while the storage client is a container-level dependency.
    """
    return ImageUrlResolver(image_repository=ImageRepository(session), object_storage=container.object_storage)


ImageUrlResolverDep = Annotated[ImageUrlResolver, Depends(get_image_url_resolver)]
