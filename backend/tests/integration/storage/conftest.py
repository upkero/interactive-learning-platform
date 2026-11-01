"""Integration fixtures: real MinIO (AIStor) from infra/compose.

These tests exercise the S3 facade against the live MinIO service; run
them where compose is up (locally, or in CI where the workflow raises
the service for the backend job and a non-reachable MinIO is a failure,
mirroring the database setup of story 1.2).
"""

import os

import httpx
import pytest

from src.app.core.settings.storage import StorageSettings, get_storage_settings
from src.app.storage.s3_object_storage_client import (
    S3ObjectStorageClient,
    build_ping_client,
    build_s3_client,
)


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
    """Client over the real MinIO; skips locally when MinIO is not up."""
    if not _minio_reachable(storage_settings):
        if os.environ.get("CI") == "1":
            # CI explicitly raises MinIO for this job (as it does for
            # Postgres): a green suite must never mean "storage skipped".
            pytest.fail(f"MinIO must be up on CI, but nothing answered at {storage_settings.endpoint_url}")
        pytest.skip(
            "MinIO is not reachable on "
            f"{storage_settings.endpoint_url}; run 'docker compose -f infra/compose.yml up -d minio minio-init' "
            "to exercise ticket 1.3.1 acceptance against the real storage."
        )
    storage = S3ObjectStorageClient(
        settings=storage_settings,
        client=build_s3_client(storage_settings, endpoint_url=storage_settings.endpoint_url),
        presign_client=build_s3_client(storage_settings, endpoint_url=storage_settings.public_endpoint_url),
        ping_client=build_ping_client(storage_settings),
    )
    assert await storage.ping(), "MinIO is reachable but ping() failed: check credentials and buckets"
    return storage
