"""Integration fixtures: real MinIO (AIStor) from infra/compose.

The MinIO service is not part of the CI backend job (the AIStor image
started; the community image is stale), so these tests only run where
compose is up (locally, or later with a proper CI service). When MinIO
is not reachable the storage integration suite is skipped so local
unit-only runs and CI stay green — acceptance for ticket 1.3.1 is
verified by running this suite against compose.
"""

import httpx
import pytest

from src.app.core.settings.storage import StorageSettings, get_storage_settings
from src.app.storage.s3_object_storage_client import S3ObjectStorageClient, build_s3_client


@pytest.fixture(scope="session")
def storage_settings() -> StorageSettings:
    return get_storage_settings()


def _minio_reachable(settings: StorageSettings) -> bool:
    try:
        response = httpx.get(f"{settings.endpoint_url.rstrip('/')}/minio/health/live", timeout=2.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture
async def object_storage(storage_settings: StorageSettings) -> S3ObjectStorageClient:
    """Client over the real MinIO; skips the suite when MinIO is not up."""
    if not _minio_reachable(storage_settings):
        pytest.skip(
            "MinIO is not reachable on "
            f"{storage_settings.endpoint_url}; run 'docker compose -f infra/compose.yml up -d minio minio-init' "
            "to exercise ticket 1.3.1 acceptance against the real storage."
        )
    storage = S3ObjectStorageClient(
        settings=storage_settings,
        client=build_s3_client(storage_settings, endpoint_url=storage_settings.endpoint_url),
        presign_client=build_s3_client(storage_settings, endpoint_url=storage_settings.public_endpoint_url),
    )
    assert await storage.ping(), "MinIO is reachable but ping() failed: check credentials and buckets"
    return storage
