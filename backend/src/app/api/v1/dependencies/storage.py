"""Object storage dependency."""

from typing import Annotated

from fastapi import Depends

from src.app.api.v1.dependencies.container import ContainerDep
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient


def get_object_storage(container: ContainerDep) -> ObjectStorageClient:
    """Single shared S3 client over MinIO (boto3 inside ``storage/``)."""
    return container.object_storage


ObjectStorageClientDep = Annotated[ObjectStorageClient, Depends(get_object_storage)]
