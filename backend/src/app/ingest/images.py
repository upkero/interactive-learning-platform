"""Normalize extracted images once, without blocking the event loop."""

import hashlib
import logging
import re
from dataclasses import dataclass, replace
from io import BytesIO
from uuid import UUID

from anyio import to_thread
from PIL import Image

from src.app.ingest.markdown_syntax import parse_markdown
from src.app.ingest.parsers.base import ExtractedImage
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.storage.object_keys import image_key

logger = logging.getLogger(__name__)
_LEADING_EMPTY_LINES = re.compile(r"^(?:[ \t]*\n)+")
_TRAILING_EMPTY_LINES = re.compile(r"\n(?:[ \t]*\n)*\Z")


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
                    replace(image, data=output.getvalue(), media_type="image/png"),
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
        extracted = {image.ref for image in images}
        kept = {item.image.ref for item in saved}
        return _format_markers(markdown, extracted, kept), tuple(saved)


def _format_markers(markdown: str, extracted: set[str], kept: set[str]) -> str:
    if not extracted:
        return markdown
    parts: list[str] = []
    cursor = 0
    for start, ref in parse_markdown(markdown).markers:
        if ref not in extracted:
            continue
        prose = markdown[cursor:start]
        if cursor:
            prose = _LEADING_EMPTY_LINES.sub("", prose)
        if prose := _TRAILING_EMPTY_LINES.sub("", prose):
            parts.append(prose)
        end = start + len(f'::image{{id="{ref}"}}')
        if ref in kept:
            parts.append(markdown[start:end])
        cursor = end
    if not cursor:
        return markdown
    if tail := _LEADING_EMPTY_LINES.sub("", markdown[cursor:]):
        parts.append(tail)
    elif parts and markdown.endswith("\n"):
        parts[-1] += "\n"
    return "\n\n".join(parts)
