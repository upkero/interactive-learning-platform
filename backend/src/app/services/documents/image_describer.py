import asyncio
import base64
import re
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.llm.text_part import TextPart
from src.app.ingest.parsers.base import ExtractedImage
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.structured import call_structured
from src.app.services.documents.prompts import VISION_SYSTEM


class ImageDescription(BaseModel):
    kind: Literal["diagram", "chart", "table", "formula", "photo", "decorative"]
    description: str = Field(min_length=1)


class StructuredCall(Protocol):
    async def __call__[T: BaseModel](
        self, llm: LLMClient, request: LLMRequest, schema: type[T], *, retries: int = 1
    ) -> T: ...


class ImageDescriber:
    def __init__(
        self,
        llm: LLMClient,
        *,
        call: StructuredCall = call_structured,
        max_images: int = 40,
        concurrency: int = 4,
    ) -> None:
        self._llm = llm
        self._call = call
        self._max_images = max_images
        self._concurrency = concurrency

    async def describe(
        self, images: tuple[ExtractedImage, ...], *, document_context: str = ""
    ) -> dict[str, str | None]:
        semaphore = asyncio.Semaphore(self._concurrency)

        async def one(image: ExtractedImage) -> tuple[str, str | None]:
            async with semaphore:
                marker = f'::image{{id="{image.ref}"}}'
                position = document_context.find(marker)
                position = max(0, position)
                surrounding = document_context[max(0, position - 250) : position + len(marker) + 250]
                headings = re.findall(r"^#{1,3}\s+(.+)$", document_context[:position], re.MULTILINE)
                topic = headings[-1] if headings else "Вступление"
                request = LLMRequest(
                    purpose="vision",
                    system=(SystemBlock(VISION_SYSTEM, cache=True),),
                    messages=(
                        LLMMessage(
                            role="user",
                            content=(
                                TextPart(
                                    f"<document_context>Topic: {topic}\nCaption: {image.caption or ''}\n"
                                    f"{surrounding}</document_context>"
                                ),
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
                    return image.ref, None

        selected = images[: self._max_images]
        values = dict(await asyncio.gather(*(one(image) for image in selected)))
        values.update({image.ref: image.caption for image in images[self._max_images :]})
        return values
