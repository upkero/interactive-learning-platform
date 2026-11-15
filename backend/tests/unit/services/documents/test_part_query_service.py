"""Part access and safe public content."""

from dataclasses import replace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import ImageDraft, MaterialRole, PartDraft, PartStatus
from src.app.contracts.widgets import WidgetKind
from src.app.exceptions.documents import PartNotFoundError
from src.app.schemas.parts import PartContentOut
from src.app.services.documents.part_query_service import PartQueryService
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import (
    FakeDocumentPartRepository,
    FakeImageRepository,
    FakeUserMaterialRepository,
)
from tests.support.fakes.repositories.widgets import FakeWidgetRepository
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient

pytestmark = pytest.mark.unit


def _service(
    *,
    parts: FakeDocumentPartRepository,
    images: FakeImageRepository,
    materials: FakeUserMaterialRepository,
    widgets: FakeWidgetRepository,
    storage: FakeObjectStorageClient,
) -> PartQueryService:
    session = FakeSession()
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    return PartQueryService(
        session_factory=factory,
        parts=lambda _: parts,
        materials=lambda _: materials,
        images=lambda _: images,
        widgets=lambda _: widgets,
        storage=storage,
    )


async def test_part_content_is_safe_and_resolves_three_directives() -> None:
    user, doc = uuid4(), uuid4()
    parts, images, materials, widgets = (
        FakeDocumentPartRepository(),
        FakeImageRepository(),
        FakeUserMaterialRepository(),
        FakeWidgetRepository(),
    )
    await materials.create(user_id=user, document_id=doc, role=MaterialRole.SHARED)
    (image,) = await images.add_many(doc, [ImageDraft(object_key="img.png", width=100, height=100)])
    code = await widgets.create(kind=WidgetKind.CODE, compiled_js="export default 1")
    config = await widgets.create(kind=WidgetKind.CONFIG, primitive_id="graph", mode="default", params={"x": 1})
    (part,) = await parts.add_many(
        doc, [PartDraft(index=0, title="Page", topic_ids=[], source_markdown="x", token_count=1)]
    )
    original: dict[str, Any] = {
        "markdown": "text",
        "images": [{"image_id": str(image.id)}],
        "widgets": [{"widget_id": str(code.id)}, {"widget_id": str(config.id)}],
        "quizzes": [{"quiz_key": "q", "correct_index": 0, "explanation": "secret", "options": [{"is_correct": True}]}],
    }
    parts._parts[part.id] = replace(part, status=PartStatus.PUBLISHED, content=original)
    service = _service(
        parts=parts,
        images=images,
        materials=materials,
        widgets=widgets,
        storage=FakeObjectStorageClient(),
    )
    details = await service.get(user_id=user, part_id=part.id)
    assert details.content is not None
    public = PartContentOut.model_validate(details.content).model_dump()
    assert public["images"][0]["url"].startswith("http://storage.local/images/img.png")
    assert public["widgets"][0]["compiled_js"] == "export default 1"
    assert public["widgets"][1]["primitive_id"] == "graph"
    assert public["quizzes"] == [{"quiz_key": "q", "options": [{}]}]
    assert original["quizzes"][0]["correct_index"] == 0
    with pytest.raises(PartNotFoundError):
        await service.get(user_id=uuid4(), part_id=part.id)


async def test_unpublished_part_has_no_content() -> None:
    user, doc = uuid4(), uuid4()
    parts, images, materials = FakeDocumentPartRepository(), FakeImageRepository(), FakeUserMaterialRepository()
    await materials.create(user_id=user, document_id=doc, role=MaterialRole.OWNER)
    (part,) = await parts.add_many(
        doc, [PartDraft(index=0, title="Page", topic_ids=[], source_markdown="x", token_count=1)]
    )
    service = _service(
        parts=parts,
        images=images,
        materials=materials,
        widgets=FakeWidgetRepository(),
        storage=FakeObjectStorageClient(),
    )
    assert (await service.get(user_id=user, part_id=part.id)).content is None
