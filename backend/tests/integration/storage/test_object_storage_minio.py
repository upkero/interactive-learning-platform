"""Integration tests 1.3.1: S3 client against real MinIO from compose.

Acceptance criteria covered here:
- put_object -> get_object round trip returns the same bytes;
- get_object of a missing key raises ObjectNotFoundError;
- presigned URLs are signed for the public endpoint (never the internal
  ``minio`` host) and expire after TTL.
"""

import asyncio
from uuid import uuid4

import httpx
import pytest

from src.app.exceptions.storage import ObjectNotFoundError
from src.app.interfaces.storage.object_storage_client import StorageBucket
from src.app.storage.object_keys import source_key
from src.app.storage.s3_object_storage_client import S3ObjectStorageClient

pytestmark = pytest.mark.integration

_AFTER_TTL_GRACE_SECONDS = 1.5


async def test_round_trip_in_both_buckets(object_storage: S3ObjectStorageClient) -> None:
    for bucket in ("documents", "images"):
        key = f"tests/{uuid4()}.txt"
        try:
            await object_storage.put_object(bucket=bucket, key=key, data=b"roundtrip", content_type="text/plain")
            assert await object_storage.get_object(bucket=bucket, key=key) == b"roundtrip"
        finally:
            await object_storage.delete_object(bucket=bucket, key=key)
        with pytest.raises(ObjectNotFoundError):
            await object_storage.get_object(bucket=bucket, key=key)


async def test_missing_key_raises_object_not_found(object_storage: S3ObjectStorageClient) -> None:
    bucket: StorageBucket = "documents"
    with pytest.raises(ObjectNotFoundError) as exc_info:
        await object_storage.get_object(bucket=bucket, key=f"tests/{uuid4()}/missing.bin")
    assert exc_info.value.error_code == "object_not_found"


async def test_presigned_url_points_to_public_endpoint_and_opens(
    object_storage: S3ObjectStorageClient,
) -> None:
    key = source_key(uuid4(), uuid4(), "txt")
    try:
        await object_storage.put_object(bucket="documents", key=key, data=b"presigned", content_type="text/plain")
        url = object_storage.presign_get_url(bucket="documents", key=key, expires_seconds=120)

        # SigV4 signs the host: the link must be usable from a browser,
        # i.e. address the public endpoint, not the internal minio host.
        assert ":9000" in url or "localhost" in url or "files." in url.split("/")[2]
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        assert response.status_code == 200
        assert response.content == b"presigned"
    finally:
        await object_storage.delete_object(bucket="documents", key=key)


async def test_presigned_url_expires_after_ttl(object_storage: S3ObjectStorageClient) -> None:
    url = object_storage.presign_get_url(
        bucket="documents",
        key=f"tests/{uuid4()}.txt",
        expires_seconds=1,
    )
    async with httpx.AsyncClient() as client:
        fresh = await client.get(url)
        # the object does not exist, so an unexpired link answers 404, an
        # expired one 403 — this keeps the test independent of the storage
        assert fresh.status_code == 404

        await asyncio.sleep(_AFTER_TTL_GRACE_SECONDS)
        expired = await client.get(url)
        assert expired.status_code == 403
