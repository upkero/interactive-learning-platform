"""Unit tests of ``ImageUrlResolver`` (story 1.3.2)."""

from uuid import uuid4

import pytest

from src.app.contracts.documents.image_draft import ImageDraft
from src.app.services.documents.image_url_resolver import ImageUrlResolver
from tests.support.fakes.repositories.documents import FakeImageRepository
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient

pytestmark = pytest.mark.unit


@pytest.fixture
def fake_images() -> FakeImageRepository:
    return FakeImageRepository()


@pytest.fixture
def fake_storage() -> FakeObjectStorageClient:
    return FakeObjectStorageClient()


@pytest.fixture
def resolver(fake_images: FakeImageRepository, fake_storage: FakeObjectStorageClient) -> ImageUrlResolver:
    return ImageUrlResolver(image_repository=fake_images, object_storage=fake_storage)


async def test_resolve_empty_input(resolver: ImageUrlResolver) -> None:
    assert await resolver.resolve([]) == {}


async def test_resolve_signs_every_image_key(
    resolver: ImageUrlResolver,
    fake_images: FakeImageRepository,
    fake_storage: FakeObjectStorageClient,
) -> None:
    document_id = uuid4()
    records = await fake_images.add_many(
        document_id,
        [
            ImageDraft(object_key=f"images/{document_id}/img_1.png", width=1, height=1, page=1),
            ImageDraft(object_key=f"images/{document_id}/img_2.png", width=2, height=2, page=2),
        ],
    )
    urls = await resolver.resolve([record.id for record in records])

    assert set(urls) == {record.id for record in records}
    assert set(fake_storage.presign_get_url_calls) == {("images", record.object_key, None) for record in records}
    # the fake URL embeds the bucket and the stored key verbatim
    assert urls[records[0].id].endswith(f"images/{records[0].object_key}?expires=3600")


async def test_resolve_skips_missing_ids(resolver: ImageUrlResolver) -> None:
    urls = await resolver.resolve([uuid4(), uuid4()])
    assert urls == {}


async def test_resolve_deduplicates_input_ids(
    resolver: ImageUrlResolver,
    fake_images: FakeImageRepository,
    fake_storage: FakeObjectStorageClient,
) -> None:
    document_id = uuid4()
    (record,) = await fake_images.add_many(
        document_id,
        [ImageDraft(object_key=f"images/{document_id}/img_1.png", width=1, height=1, page=1)],
    )
    urls = await resolver.resolve([record.id, record.id])

    assert list(urls) == [record.id]
    assert len(fake_storage.presign_get_url_calls) == 2  # one per requested id
