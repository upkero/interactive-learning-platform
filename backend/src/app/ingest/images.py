"""Normalize extracted images once, without blocking the event loop."""

import hashlib
import logging
import re
from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

from anyio import to_thread
from PIL import Image

from src.app.ingest.parsers.base import ExtractedImage
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.storage.object_keys import image_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StoredImage:
    image: ExtractedImage
    key: str
    width: int
    height: int


def _normalize(images: tuple[ExtractedImage, ...]) -> tuple[tuple[ExtractedImage, int, int], ...]:
    result: list[tuple[ExtractedImage, int, int]] = []
    seen: set[bytes] = set()
    for image in images:
        try:
            with Image.open(BytesIO(image.data)) as source:
                value = source.convert("RGBA")
            if value.width < 48 or value.height < 48:
                continue
            digest = hashlib.sha256(
                value.width.to_bytes(4, "big") + value.height.to_bytes(4, "big") + value.tobytes()
            ).digest()
            if digest in seen:
                continue
            seen.add(digest)
            value.thumbnail((1600, 1600))
            output = BytesIO()
            value.save(output, format="PNG", optimize=True)
            result.append(
                (
                    ExtractedImage(
                        ref=image.ref,
                        data=output.getvalue(),
                        media_type="image/png",
                        page=image.page,
                        caption=image.caption,
                    ),
                    value.width,
                    value.height,
                )
            )
        except Exception:
            logger.warning("Invalid extracted image", extra={"image_ref": image.ref}, exc_info=True)
    return tuple(result)


class ImageStore:
    """Save valid PNG images, retaining the original reference numbers."""

    def __init__(self, storage: ObjectStorageClient) -> None:
        self._storage = storage

    async def save(
        self, document_id: UUID, markdown: str, images: tuple[ExtractedImage, ...]
    ) -> tuple[str, tuple[StoredImage, ...]]:
        normalized = await to_thread.run_sync(_normalize, images)
        await self._storage.delete_prefix(bucket="images", prefix=f"{document_id}/")
        saved: list[StoredImage] = []
        for image, width, height in normalized:
            try:
                if not re.fullmatch(r"img_[1-9]\d*", image.ref):
                    raise ValueError("Invalid image reference")
                key = image_key(document_id, int(image.ref.removeprefix("img_")))
                await self._storage.put_object(bucket="images", key=key, data=image.data, content_type="image/png")
                saved.append(StoredImage(image=image, key=key, width=width, height=height))
            except Exception:
                logger.warning("Could not store extracted image", extra={"image_ref": image.ref}, exc_info=True)
        kept = {item.image.ref for item in saved}
        for image in images:
            if image.ref not in kept:
                marker = re.escape(f'::image{{id="{image.ref}"}}')
                markdown = re.sub(rf"\n*{marker}\n*", "\n\n", markdown, count=1)
        markdown = re.sub(r'(\n{3,})(?=::image\{id="img_\d+"\})', "\n\n", markdown)
        markdown = re.sub(r'(::image\{id="img_\d+"\})\n{3,}', r"\1\n\n", markdown)
        return markdown, tuple(saved)
