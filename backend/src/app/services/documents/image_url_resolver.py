"""Presigned URL resolver for part images (story 1.3.2).

``GET /parts/{id}`` (1.4.8) stores only ``image_id`` in the part content;
browser links are signed per response with TTL ``S3_PRESIGN_TTL_SECONDS``
— URLs are never persisted, they would expire. The resolver looks up the
stored object keys in ``ImageRepository`` and signs them through the
``ObjectStorageClient`` (the presign boto3 client is bound to
``S3_PUBLIC_ENDPOINT_URL``, so hosts match what the browser can reach).
"""

from collections.abc import Sequence
from uuid import UUID

from src.app.interfaces.repositories.documents import ImageRepositoryProtocol
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient


class ImageUrlResolver:
    """Resolves ``image_id -> presigned GET url`` for a part's images."""

    def __init__(
        self,
        *,
        image_repository: ImageRepositoryProtocol,
        object_storage: ObjectStorageClient,
    ) -> None:
        self._images = image_repository
        self._storage = object_storage

    async def resolve(self, image_ids: Sequence[UUID]) -> dict[UUID, str]:
        """Presign every image id that still exists; missing ids are skipped.

        One repository query, then one local signing per image
        (``presign_get_url`` never touches the network, no to_thread).
        Duplicated ids in the input share one signed URL in the result.
        """
        if not image_ids:
            return {}
        records = await self._images.get_many(list(image_ids))
        return {record.id: self._storage.presign_get_url(bucket="images", key=record.object_key) for record in records}
