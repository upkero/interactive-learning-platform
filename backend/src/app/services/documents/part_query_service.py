"""Read accessible published parts without disclosing quiz solutions."""

from copy import deepcopy
from typing import Any
from uuid import UUID

from src.app.contracts.documents.part_details import PartDetails
from src.app.contracts.documents.statuses import PartStatus
from src.app.exceptions.documents import PartNotFoundError
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    ImageRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.repositories.widgets import WidgetRepositoryProtocol
from src.app.services.documents.image_url_resolver import ImageUrlResolver

_SECRET_QUIZ_FIELDS = frozenset(
    {
        "correct",
        "correct_index",
        "correct_indices",
        "correct_answer",
        "correct_answers",
        "explanation",
        "option_explanations",
        "is_correct",
        "answer",
        "answers",
        "tolerance",
    }
)


def _public_quiz(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _public_quiz(v) for k, v in value.items() if k not in _SECRET_QUIZ_FIELDS}
    if isinstance(value, list):
        return [_public_quiz(v) for v in value]
    return value


class PartQueryService:
    def __init__(
        self,
        *,
        parts: DocumentPartRepositoryProtocol,
        materials: UserMaterialRepositoryProtocol,
        images: ImageRepositoryProtocol,
        resolver: ImageUrlResolver,
        widgets: WidgetRepositoryProtocol,
    ) -> None:
        self._parts = parts
        self._materials = materials
        self._images = images
        self._resolver = resolver
        self._widgets = widgets

    async def get(self, *, user_id: UUID, part_id: UUID) -> PartDetails:
        part = await self._parts.get(part_id)
        if part is None or await self._materials.get_role(user_id, part.document_id) is None:
            raise PartNotFoundError()
        if part.status is not PartStatus.PUBLISHED or part.content is None:
            return PartDetails(part=part, content=None)

        content = deepcopy(part.content)
        content["quizzes"] = _public_quiz(content.get("quizzes", []))
        for directive in content.get("widgets", []):
            widget_id = directive.get("widget_id")
            if widget_id is None:
                continue
            widget = await self._widgets.get(UUID(str(widget_id)))
            if widget is None:
                continue
            if widget.kind.value == "code":
                directive["compiled_js"] = widget.compiled_js
            else:
                directive.update(primitive_id=widget.primitive_id, mode=widget.mode, params=widget.params)
        image_records = await self._images.list_by_document(part.document_id)
        image_ids = {str(image.id): image.id for image in image_records}
        urls = await self._resolver.resolve(list(image_ids.values()))

        def replace_images(value: Any) -> None:
            if isinstance(value, dict):
                image_id = image_ids.get(str(value.get("image_id")))
                if image_id is not None and image_id in urls:
                    value["url"] = urls[image_id]
                for child in value.values():
                    replace_images(child)
            elif isinstance(value, list):
                for child in value:
                    replace_images(child)

        replace_images(content)
        return PartDetails(part=part, content=content)
