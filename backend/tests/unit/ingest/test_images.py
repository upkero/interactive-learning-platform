from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from src.app.ingest.images import ImageStore
from src.app.ingest.parsers.base import ExtractedImage
from src.app.interfaces.storage.object_storage_client import StorageBucket
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient


def png(width: int, height: int, color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_references_match_saved_images_after_filter_and_failure() -> None:
    class FailedImageStorage(FakeObjectStorageClient):
        async def put_object(self, *, bucket: StorageBucket, key: str, data: bytes, content_type: str) -> None:
            if key.endswith("img_5.png"):
                raise RuntimeError("failed upload")
            await super().put_object(bucket=bucket, key=key, data=data, content_type=content_type)

    document_id = uuid4()
    storage = FailedImageStorage(objects={("images", f"{document_id}/orphan.png"): b"old"})
    first = png(100, 100, "red")
    images = (
        ExtractedImage(ref="img_1", data=first, media_type="image/png"),
        ExtractedImage(ref="img_2", data=png(20, 20, "blue"), media_type="image/png"),
        ExtractedImage(ref="img_3", data=png(200, 100, "green"), media_type="image/png"),
        ExtractedImage(ref="img_4", data=first, media_type="image/png"),
        ExtractedImage(ref="img_5", data=png(150, 100, "yellow"), media_type="image/png"),
    )
    code = 'Example: `begin\n::image{id="img_2"}\nend`'
    markers = "\n\n\n".join(f'::image{{id="{image.ref}"}}' for image in images)
    markdown = f"# Topic\n\n \n\n{markers}\n\n\n{code}\n"
    markdown, saved = await ImageStore(storage).save(document_id, markdown, images)
    assert [item.image.ref for item in saved] == ["img_1", "img_3"]
    assert [item.key for item in saved] == [f"{document_id}/img_1.png", f"{document_id}/img_3.png"]
    assert markdown == f'# Topic\n\n::image{{id="img_1"}}\n\n::image{{id="img_3"}}\n\n{code}\n'
    assert ("images", f"{document_id}/orphan.png") in storage.delete_object_calls
