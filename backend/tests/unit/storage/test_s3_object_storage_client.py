"""Unit tests of ``S3ObjectStorageClient`` with a duck-typed boto3 stub.

The stub mimics the used subset of the botocore S3 client (no network)
so the tests cover ``asyncio.to_thread`` usage, bucket mapping, error
code mapping and presign client selection without real MinIO.
"""

import io
from typing import Any

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from src.app.core.settings.storage import StorageSettings
from src.app.exceptions.storage import ObjectNotFoundError, ObjectStorageError
from src.app.storage.s3_object_storage_client import S3ObjectStorageClient

pytestmark = pytest.mark.unit


class _StubS3Client:
    """Subset of the boto3 S3 client API used by ``S3ObjectStorageClient``."""

    def __init__(self, *, objects: dict[str, bytes] | None = None, error: Exception | None = None) -> None:
        self.objects: dict[str, bytes] = dict(objects or {})
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def put_object(self, **kwargs: Any) -> None:
        self._record("put_object", kwargs)
        self._raise_if_configured()
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self._record("get_object", kwargs)
        self._raise_if_configured()
        data = self.objects.get(kwargs["Key"])
        if data is None:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")
        return {"Body": io.BytesIO(data)}

    def delete_object(self, **kwargs: Any) -> None:
        self._record("delete_object", kwargs)
        self._raise_if_configured()
        self.objects.pop(kwargs["Key"], None)

    def head_bucket(self, **kwargs: Any) -> None:
        self._record("head_bucket", kwargs)
        self._raise_if_configured()

    def generate_presigned_url(
        self,
        operation_name: str,
        *,
        # capitalized kwargs keep the botocore call-site shape
        Params: dict[str, Any],
        ExpiresIn: int,
    ) -> str:
        self._record("generate_presigned_url", {"Op": operation_name, **Params, "ExpiresIn": ExpiresIn})
        self._raise_if_configured()
        return f"https://stub.example/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"

    def _raise_if_configured(self) -> None:
        if self.error is not None:
            raise self.error

    def _record(self, operation: str, kwargs: dict[str, Any]) -> None:
        self.calls.append((operation, kwargs))


def _build(settings: StorageSettings, client: _StubS3Client, presign: _StubS3Client) -> S3ObjectStorageClient:
    """Wire the S3 facade around stub boto3 clients (they are structurally fine)."""
    return S3ObjectStorageClient(settings=settings, client=client, presign_client=presign)


@pytest.fixture
def settings() -> StorageSettings:
    return StorageSettings()


@pytest.fixture
def stub_client() -> _StubS3Client:
    return _StubS3Client()


@pytest.fixture
def stub_presign_client() -> _StubS3Client:
    return _StubS3Client()


@pytest.fixture
def client(
    settings: StorageSettings,
    stub_client: _StubS3Client,
    stub_presign_client: _StubS3Client,
) -> S3ObjectStorageClient:
    return _build(settings, stub_client, stub_presign_client)


def _calls_of(stub: _StubS3Client, operation: str) -> list[dict[str, Any]]:
    return [kwargs for name, kwargs in stub.calls if name == operation]


async def test_put_get_delete_round_trip(
    client: S3ObjectStorageClient,
    stub_client: _StubS3Client,
    settings: StorageSettings,
) -> None:
    await client.put_object(bucket="documents", key="k", data=b"bytes", content_type="text/plain")
    assert await client.get_object(bucket="documents", key="k") == b"bytes"

    await client.delete_object(bucket="documents", key="k")
    with pytest.raises(ObjectNotFoundError):
        await client.get_object(bucket="documents", key="k")

    (put_call,) = _calls_of(stub_client, "put_object")
    assert put_call["Bucket"] == settings.bucket_documents
    assert put_call["ContentType"] == "text/plain"


async def test_bucket_mapping(settings: StorageSettings, stub_client: _StubS3Client) -> None:
    client = _build(settings, stub_client, _StubS3Client())
    await client.put_object(bucket="images", key="k", data=b"x", content_type="image/png")
    (put_call,) = _calls_of(stub_client, "put_object")
    assert put_call["Bucket"] == settings.bucket_images


async def test_missing_key_maps_to_object_not_found(client: S3ObjectStorageClient) -> None:
    with pytest.raises(ObjectNotFoundError) as exc_info:
        await client.get_object(bucket="images", key="no-such-key")
    assert exc_info.value.status_code == 404
    assert exc_info.value.error_code == "object_not_found"


async def test_denied_access_maps_to_object_storage_error(
    settings: StorageSettings,
    stub_client: _StubS3Client,
) -> None:
    stub_client.error = ClientError({"Error": {"Code": "AccessDenied"}}, "get_object")
    client = _build(settings, stub_client, _StubS3Client())
    with pytest.raises(ObjectStorageError) as exc_info:
        await client.get_object(bucket="documents", key="k")
    assert exc_info.value.status_code == 502
    assert exc_info.value.error_code == "object_storage_error"


async def test_botocore_error_on_put_maps_to_object_storage_error(
    settings: StorageSettings,
    stub_client: _StubS3Client,
) -> None:
    stub_client.error = BotoCoreError()
    client = _build(settings, stub_client, _StubS3Client())
    with pytest.raises(ObjectStorageError):
        await client.put_object(bucket="documents", key="k", data=b"x", content_type="text/plain")


def test_presign_uses_the_presign_client_with_public_host(
    client: S3ObjectStorageClient,
    stub_client: _StubS3Client,
    stub_presign_client: _StubS3Client,
    settings: StorageSettings,
) -> None:
    url = client.presign_get_url(bucket="documents", key="k")
    assert url.startswith("https://stub.example/")
    # the working client must never sign URLs
    assert _calls_of(stub_client, "generate_presigned_url") == []
    (presign_call,) = _calls_of(stub_presign_client, "generate_presigned_url")
    assert presign_call["Bucket"] == settings.bucket_documents
    assert presign_call["ExpiresIn"] == settings.presign_ttl_seconds


def test_presign_custom_ttl(client: S3ObjectStorageClient, stub_presign_client: _StubS3Client) -> None:
    client.presign_get_url(bucket="images", key="k", expires_seconds=60)
    (presign_call,) = _calls_of(stub_presign_client, "generate_presigned_url")
    assert presign_call["ExpiresIn"] == 60


async def test_ping_checks_both_buckets(settings: StorageSettings, stub_client: _StubS3Client) -> None:
    client = _build(settings, stub_client, _StubS3Client())
    assert await client.ping() is True
    pings = _calls_of(stub_client, "head_bucket")
    assert {call["Bucket"] for call in pings} == {settings.bucket_documents, settings.bucket_images}


async def test_ping_false_when_minio_down(settings: StorageSettings, stub_client: _StubS3Client) -> None:
    stub_client.error = ClientError({"Error": {"Code": "AccessDenied"}}, "head_bucket")
    client = _build(settings, stub_client, _StubS3Client())
    assert await client.ping() is False
