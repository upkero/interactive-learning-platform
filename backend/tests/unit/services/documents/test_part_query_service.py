"""Part access and safe public content."""

import json
from dataclasses import replace
from pathlib import Path
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


def test_seed_public_content_cannot_contain_answer_keys() -> None:
    fixture = Path(__file__).resolve().parents[3] / "support/fixtures/seed/published_part.json"
    content = json.loads(fixture.read_text())["content"]
    with pytest.raises(ValueError):
        PartContentOut.model_validate(content)
    content.pop("answer_keys")
    assert "answer_keys" not in PartContentOut.model_validate(content).model_dump()


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
        "schema_version": 1,
        "title": "Page",
        "markdown": "text",
        "images": {"img": {"image_id": str(image.id)}},
        "widgets": {
            "w1": {"status": "ready", "kind": "code", "title": "Code", "widget_id": str(code.id)},
            "w2": {"status": "ready", "kind": "config", "title": "Config", "widget_id": str(config.id)},
        },
        "quizzes": [
            {
                "key": "q",
                "ref": "q1",
                "type": "single_choice",
                "prompt": "Question",
                "options": [{"id": "a", "text": "A", "is_correct": True}],
            }
        ],
        "answer_keys": {"q": {"correct_id": "a", "explanation": "secret"}},
        "private_pipeline_detail": "must not reach callers",
        "sections": [
            {"title": "Unmatched", "anchor": "unmatched", "topic_id": None, "source_span": None, "page": None}
        ],
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
    assert public["images"]["img"]["url"].startswith("http://storage.local/images/img.png")
    assert public["widgets"]["w1"]["compiled_js"] == "export default 1"
    assert public["widgets"]["w2"]["primitive_id"] == "graph"
    assert public["quizzes"][0]["options"] == [{"id": "a", "text": "A"}]
    assert "answer_keys" not in public
    assert public["sections"][0]["topic_id"] is None
    assert public["sections"][0]["source_span"] is None
    assert "private_pipeline_detail" not in details.content
    assert original["answer_keys"]["q"]["correct_id"] == "a"
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
