"""Read accessible published parts without disclosing quiz solutions."""

from collections.abc import Callable
from contextlib import suppress
from copy import deepcopy
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.part_details import PartDetails
from src.app.contracts.documents.statuses import PartStatus
from src.app.exceptions.documents import PartNotFoundError
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    ImageRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.repositories.widgets import WidgetRepositoryProtocol
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.services.documents.image_url_resolver import ImageUrlResolver

_PUBLIC_CONTENT_FIELDS = frozenset(
    {"schema_version", "title", "markdown", "key_terms", "widgets", "images", "quizzes", "sources", "sections"}
)


def _public_quiz(quiz: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {key: quiz[key] for key in ("key", "ref", "type", "prompt", "unit") if key in quiz}
    for field in ("options", "items"):
        if field in quiz:
            options = quiz[field]
            if not isinstance(options, list) or any(not isinstance(option, dict) for option in options):
                raise ValueError("Invalid quiz options in published content")
            result[field] = [{key: option[key] for key in ("id", "text") if key in option} for option in options]
    return result


def _collect_image_ids(value: object) -> set[UUID]:
    """Every ``image_id`` referenced by the content, in one walk."""
    found: set[UUID] = set()
    if isinstance(value, dict):
        raw = value.get("image_id")
        if raw is not None:
            with suppress(ValueError):
                found.add(UUID(str(raw)))
        for child in value.values():
            found |= _collect_image_ids(child)
    elif isinstance(value, list):
        for child in value:
            found |= _collect_image_ids(child)
    return found


class PartQueryService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        materials: Callable[[AsyncSession], UserMaterialRepositoryProtocol],
        images: Callable[[AsyncSession], ImageRepositoryProtocol],
        widgets: Callable[[AsyncSession], WidgetRepositoryProtocol],
        storage: ObjectStorageClient,
    ) -> None:
        self._session_factory = session_factory
        self._parts = parts
        self._materials = materials
        self._images = images
        self._widgets = widgets
        self._storage = storage

    async def get(self, *, user_id: UUID, part_id: UUID) -> PartDetails:
        async with self._session_factory() as session:
            part = await self._parts(session).get(part_id)
            if part is None or await self._materials(session).get_role(user_id, part.document_id) is None:
                raise PartNotFoundError()
            if part.status is not PartStatus.PUBLISHED or part.content is None:
                return PartDetails(part=part, content=None)

            content: dict[str, object] = deepcopy(
                {key: value for key, value in part.content.items() if key in _PUBLIC_CONTENT_FIELDS}
            )
            quizzes = content.get("quizzes", [])
            if not isinstance(quizzes, list) or any(not isinstance(quiz, dict) for quiz in quizzes):
                raise ValueError("Invalid quizzes in published content")
            content["quizzes"] = [_public_quiz(quiz) for quiz in quizzes]
            await self._fill_widgets(content, self._widgets(session))
            await self._fill_images(content, self._images(session))
            return PartDetails(part=part, content=content)

    async def _fill_widgets(self, content: dict[str, object], widgets: WidgetRepositoryProtocol) -> None:
        slots = content.get("widgets", {})
        if not isinstance(slots, dict):
            raise ValueError("Invalid widget slots in published content")
        if any(not isinstance(slot, dict) for slot in slots.values()):
            raise ValueError("Invalid widget slot in published content")
        directives = [d for d in slots.values() if d.get("status") == "ready" and d.get("widget_id") is not None]
        if not directives:
            return
        widget_ids = [UUID(str(d["widget_id"])) for d in directives]
        records = {record.id: record for record in await widgets.get_many(widget_ids)}
        for directive in directives:
            widget = records.get(UUID(str(directive["widget_id"])))
            if widget is None:
                continue
            if widget.kind.value == "code":
                directive["compiled_js"] = widget.compiled_js
            else:
                directive.update(primitive_id=widget.primitive_id, mode=widget.mode, params=widget.params)

    async def _fill_images(
        self,
        content: dict[str, object],
        images: ImageRepositoryProtocol,
    ) -> None:
        image_ids = _collect_image_ids(content)
        if not image_ids:
            return
        resolver = ImageUrlResolver(image_repository=images, object_storage=self._storage)
        urls = await resolver.resolve(list(image_ids))

        def replace_images(value: object) -> None:
            if isinstance(value, dict):
                raw = value.get("image_id")
                if raw is not None:
                    try:
                        image_id = UUID(str(raw))
                    except ValueError:
                        image_id = None
                    if image_id is not None and image_id in urls:
                        value["url"] = urls[image_id]
                for child in value.values():
                    replace_images(child)
            elif isinstance(value, list):
                for child in value:
                    replace_images(child)

        replace_images(content)


__all__ = ["PartQueryService"]
