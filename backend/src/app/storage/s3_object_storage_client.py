"""S3 implementation of ``ObjectStorageClient`` over the synchronous boto3 SDK.

boto3 blocks, so every network call is moved to a worker thread with
``asyncio.to_thread`` (story 1.3 rule; unlike faq-assistant, the event
loop must never wait on S3). ``generate_presigned_url`` is local signing
without a network hop, so it stays on the loop.

Two boto3 clients are used: the working one on ``S3_ENDPOINT_URL`` and
the URL signer on ``S3_PUBLIC_ENDPOINT_URL`` — SigV4 signs the host, so
browser links must point to the public address (in dev ``localhost:9000``,
in prod ``https://files.<domain>``), never to the internal ``minio:9000``.
"""

import asyncio
from contextlib import closing
from typing import cast

import boto3
from botocore.client import BaseClient, Config
from botocore.exceptions import BotoCoreError, ClientError

from src.app.core.settings.storage import StorageSettings
from src.app.exceptions.storage import ObjectNotFoundError, ObjectStorageError
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient, StorageBucket

_NOT_FOUND_CODES = frozenset({"NoSuchKey", "NoSuchBucket", "NotFound", "404"})


def build_s3_client(settings: StorageSettings, *, endpoint_url: str) -> BaseClient:
    """Build one boto3 S3 client against ``endpoint_url``.

    botocore clients are thread-safe and boto3 sessions are not, so the
    client is created once per container and shared between threads.
    """
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key.get_secret_value(),
        region_name=settings.region_name,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},  # MinIO works with path-style keys
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        ),
    )


class S3ObjectStorageClient(ObjectStorageClient):
    def __init__(
        self,
        *,
        settings: StorageSettings,
        client: BaseClient,
        presign_client: BaseClient,
    ) -> None:
        self._settings = settings
        self._client = client
        self._presign_client = presign_client

    def _bucket(self, bucket: StorageBucket) -> str:
        return self._settings.bucket_documents if bucket == "documents" else self._settings.bucket_images

    async def put_object(self, *, bucket: StorageBucket, key: str, data: bytes, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket(bucket),
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(f"Failed to upload object: {key}") from exc

    async def get_object(self, *, bucket: StorageBucket, key: str) -> bytes:
        try:
            return await asyncio.to_thread(self._read_object, self._bucket(bucket), key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                raise ObjectNotFoundError(f"Object not found: {key}") from exc
            raise ObjectStorageError(f"Failed to download object: {key}") from exc
        except BotoCoreError as exc:
            raise ObjectStorageError(f"Failed to download object: {key}") from exc

    def _read_object(self, real_bucket: str, key: str) -> bytes:
        """Read the body in a worker thread; the stream must be closed there."""
        response = self._client.get_object(Bucket=real_bucket, Key=key)

        with closing(response["Body"]) as body:
            return cast("bytes", body.read())

    async def delete_object(self, *, bucket: StorageBucket, key: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._bucket(bucket),
                Key=key,
            )
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStorageError(f"Failed to delete object: {key}") from exc

    def presign_get_url(
        self,
        *,
        bucket: StorageBucket,
        key: str,
        expires_seconds: int | None = None,
    ) -> str:
        # local signing, no network call — therefore no to_thread
        url = self._presign_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket(bucket), "Key": key},
            ExpiresIn=expires_seconds or self._settings.presign_ttl_seconds,
        )
        return str(url)

    async def ping(self) -> bool:
        """``head_bucket`` over both buckets; ``False`` on any S3 failure."""
        try:
            await asyncio.gather(
                asyncio.to_thread(self._client.head_bucket, Bucket=self._settings.bucket_documents),
                asyncio.to_thread(self._client.head_bucket, Bucket=self._settings.bucket_images),
            )
        except (BotoCoreError, ClientError):
            return False
        return True
