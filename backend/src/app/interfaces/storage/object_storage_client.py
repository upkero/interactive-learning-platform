"""Interface of the object storage client (MinIO, S3-compatible)."""

from abc import ABC, abstractmethod
from typing import Literal

StorageBucket = Literal["documents", "images"]


class ObjectStorageClient(ABC):
    """Storage abstraction used by services; never boto3 directly.

    ``documents`` holds uploaded sources, ``images`` holds pictures
    extracted from them (story 1.9). Every network call of the S3
    implementation runs through ``asyncio.to_thread``.
    """

    @abstractmethod
    async def put_object(
        self,
        *,
        bucket: StorageBucket,
        key: str,
        data: bytes,
        content_type: str,
    ) -> None: ...

    @abstractmethod
    async def get_object(self, *, bucket: StorageBucket, key: str) -> bytes: ...

    @abstractmethod
    async def delete_object(self, *, bucket: StorageBucket, key: str) -> None: ...

    @abstractmethod
    def presign_get_url(
        self,
        *,
        bucket: StorageBucket,
        key: str,
        expires_seconds: int | None = None,
    ) -> str: ...

    @abstractmethod
    async def ping(self) -> bool: ...
