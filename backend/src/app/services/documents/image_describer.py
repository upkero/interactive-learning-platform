import asyncio
import base64
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.llm.text_part import TextPart
from src.app.ingest.parsers.base import ExtractedImage
from src.app.llm.structured import call_structured
from src.app.services.documents.prompts import VISION_SYSTEM


class ImageDescription(BaseModel):
    kind: Literal["diagram", "chart", "table", "formula", "photo", "decorative"]
    description: str = Field(min_length=1)


class ImageDescriber:
    def __init__(self, llm: Any, *, call: Callable[..., Awaitable[Any]] = call_structured) -> None:
        self._llm = llm
        self._call = call

    async def describe(
        self, images: tuple[ExtractedImage, ...], *, document_context: str = ""
    ) -> dict[str, str | None]:
        semaphore = asyncio.Semaphore(4)

        async def one(image: ExtractedImage) -> tuple[str, str | None]:
            if image.caption and len(images) > 40:
                return image.ref, image.caption
            async with semaphore:
                request = LLMRequest(
                    purpose="vision",
                    system=(SystemBlock(VISION_SYSTEM, cache=True),),
                    messages=(
                        LLMMessage(
                            role="user",
                            content=(
                                TextPart(f"<document_context>{document_context[-500:]}</document_context>"),
                                ImagePart("image/png", base64.b64encode(image.data).decode()),
                            ),
                        ),
                    ),
                    metadata={"image_ref": image.ref},
                )
                try:
                    result = await self._call(self._llm, request, ImageDescription)
                    return image.ref, None if result.kind == "decorative" else result.description
                except Exception:
                    return image.ref, image.caption

        selected = images[:40]
        values = dict(await asyncio.gather(*(one(image) for image in selected)))
        values.update({image.ref: image.caption for image in images[40:]})
        return values
