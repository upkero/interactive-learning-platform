from typing import cast
from unittest.mock import AsyncMock

import pytest

from src.app.contracts.ingest import ExtractedImage
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.services.documents.image_describer import ImageDescriber, ImageDescription, StructuredCall


@pytest.mark.unit
@pytest.mark.asyncio
async def test_first_images_go_to_model_and_overflow_uses_caption() -> None:
    call = AsyncMock(return_value=ImageDescription(kind="diagram", description="Diagram"))
    images = tuple(
        ExtractedImage(ref=f"img_{index}", data=b"png", media_type="image/png", caption=f"caption {index}")
        for index in range(1, 42)
    )
    describer = ImageDescriber(cast(LLMClient, object()), call=cast(StructuredCall, call), max_images=40)
    results = await describer.describe(images, document_context='# Topic\n\n::image{id="img_1"}')
    assert call.await_count == 40
    assert results["img_1"] == "Diagram"
    assert results["img_41"] == "caption 41"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_or_decorative_description_is_empty() -> None:
    call = AsyncMock(side_effect=[ImageDescription(kind="decorative", description="Logo"), RuntimeError("down")])
    images = tuple(
        ExtractedImage(ref=f"img_{index}", data=b"png", media_type="image/png", caption="caption") for index in (1, 2)
    )
    describer = ImageDescriber(cast(LLMClient, object()), call=cast(StructuredCall, call))
    assert await describer.describe(images) == {"img_1": None, "img_2": None}
