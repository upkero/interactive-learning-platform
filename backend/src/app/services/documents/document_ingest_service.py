import logging
from collections.abc import Callable, Iterator
from functools import partial
from typing import Protocol
from uuid import UUID

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.statuses import DocumentErrorCode, DocumentStatus, SourceType
from src.app.contracts.progress.event_type import ProgressEventType
from src.app.core.settings.upload import get_upload_settings
from src.app.ingest.parsers.base import ExtractedImage, ParsedDocument, ParserRegistry
from src.app.ingest.parsers.gdocs_importer import GDocsImporter, GDocsImportError
from src.app.ingest.tokens import get_token_counter
from src.app.ingest.topic_tree import TopicNode, build_topic_tree
from src.app.interfaces.repositories.documents import DocumentRepositoryProtocol, ImageRepositoryProtocol
from src.app.interfaces.services.progress_notifier import ProgressNotifier
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.storage.object_keys import image_key, parsed_markdown_key, source_key

logger = logging.getLogger(__name__)


class _ImageDescriber(Protocol):
    async def describe(
        self, images: tuple[ExtractedImage, ...], *, document_context: str = ""
    ) -> dict[str, str | None]: ...


class _TopicSegmenter(Protocol):
    async def segment(self, markdown: str) -> str: ...


class DocumentIngestService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        images: Callable[[AsyncSession], ImageRepositoryProtocol],
        storage: ObjectStorageClient,
        registry: ParserRegistry,
        notifier: ProgressNotifier,
        gdocs: GDocsImporter | None = None,
        image_describer: _ImageDescriber | None = None,
        topic_segmenter: _TopicSegmenter | None = None,
    ) -> None:
        self._session_factory, self._documents, self._images = session_factory, documents, images
        self._storage, self._registry, self._notifier = storage, registry, notifier
        self._gdocs = gdocs or GDocsImporter()
        self._image_describer = image_describer
        self._topic_segmenter = topic_segmenter

    async def parse(self, document_id: UUID) -> None:
        async with self._session_factory() as session:
            document = await self._documents(session).get(document_id)
        if document is None:
            return
        await self._set_status(document_id, DocumentStatus.PARSING)
        await self._notifier.emit(document_id, ProgressEventType.STAGE, stage="parsing", message="Parsing document")
        try:
            if document.source_type is SourceType.GDOCS:
                data, title = await self._gdocs.fetch(document.source_uri or "")
                source = source_key(document.owner_id, document.id, "docx")
                await self._storage.put_object(
                    bucket="documents",
                    key=source,
                    data=data,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                await self._update_source(document_id, source, title)
                filename = "source.docx"
            else:
                data = await self._storage.get_object(bucket="documents", key=document.object_key)
                filename = document.object_key.rsplit("/", 1)[-1]
            mime = (
                document.mime_type
                if document.source_type is SourceType.UPLOAD
                else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            parser = self._registry.for_mime(mime)
            parsed = await to_thread.run_sync(partial(parser.parse, data, filename=filename))
            if not parsed.markdown.strip():
                raise IngestFailure(DocumentErrorCode.EMPTY_DOCUMENT, "Document is empty")
            if parsed.page_count is not None and parsed.page_count > get_upload_settings().max_pages:
                raise IngestFailure(DocumentErrorCode.TOO_MANY_PAGES, "Document has too many pages")
            if self._topic_segmenter is not None and not _has_heading(parsed.markdown):
                parsed = ParsedDocument(
                    markdown=await self._topic_segmenter.segment(parsed.markdown),
                    images=parsed.images,
                    page_count=parsed.page_count,
                    title=parsed.title,
                    heading_pages=parsed.heading_pages,
                )
            await self._store_result(document, parsed)
            await self._update_page_count(document_id, parsed.page_count)
            await self._set_status(document_id, DocumentStatus.PARSED)
        except GDocsImportError as exc:
            await self._fail(document_id, exc.code, str(exc))
        except IngestFailure as exc:
            await self._fail(document_id, exc.code, str(exc))
        except Exception as exc:
            logger.exception("Document parsing failed", extra={"document_id": str(document_id)})
            await self._fail(document_id, DocumentErrorCode.PARSE_FAILED, repr(exc))

    async def _store_result(self, document: object, parsed: ParsedDocument) -> None:
        document_id = document.id  # type: ignore[attr-defined]
        parsed = _normalize_images(parsed)
        tree = build_topic_tree(parsed.markdown, get_token_counter(), parsed.heading_pages)
        await self._storage.put_object(
            bucket="documents",
            key=parsed_markdown_key(document.owner_id, document_id),  # type: ignore[attr-defined]
            data=parsed.markdown.encode(),
            content_type="text/markdown; charset=utf-8",
        )
        async with self._session_factory() as session, session.begin():
            old = await self._images(session).delete_by_document(document_id)
            await self._documents(session).set_topic_tree(document_id, [node.to_dict() for node in tree])
        for record in old:
            try:
                await self._storage.delete_object(bucket="images", key=record.object_key)
            except Exception:
                logger.warning("Failed to delete old document image", extra={"object_key": record.object_key})
        await self._notifier.emit(document_id, ProgressEventType.STAGE, stage="images", message="Images extracted")
        await self._save_images(document_id, parsed.images, tree)
        if self._image_describer is not None and parsed.images:
            try:
                descriptions = await self._image_describer.describe(parsed.images, document_context=parsed.markdown)
                async with self._session_factory() as session, session.begin():
                    await self._images(session).update_descriptions(document_id, descriptions)
            except Exception:
                logger.warning(
                    "Image descriptions were not generated",
                    extra={"document_id": str(document_id)},
                    exc_info=True,
                )

    async def _save_images(self, document_id: UUID, images: tuple[ExtractedImage, ...], tree: list[TopicNode]) -> None:
        import hashlib
        from io import BytesIO

        from PIL import Image

        seen: set[str] = set()
        drafts: list[ImageDraft] = []
        for index, extracted in enumerate(images, 1):
            try:
                image = Image.open(BytesIO(extracted.data)).convert("RGBA")
                digest = hashlib.sha256(image.tobytes()).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                image.thumbnail((1600, 1600))
                output = BytesIO()
                image.save(output, format="PNG", optimize=True)
                key = image_key(document_id, index)
                await self._storage.put_object(
                    bucket="images", key=key, data=output.getvalue(), content_type="image/png"
                )
                topic_id = next((node.id for node in _walk(tree) if extracted.ref in node.image_ids), None)
                drafts.append(
                    ImageDraft(
                        object_key=key,
                        width=image.width,
                        height=image.height,
                        page=extracted.page,
                        caption=extracted.caption,
                        topic_id=topic_id,
                    )
                )
            except Exception:
                logger.warning("Could not store extracted image", extra={"image_ref": extracted.ref}, exc_info=True)
        async with self._session_factory() as session, session.begin():
            await self._images(session).add_many(document_id, drafts)

    async def _set_status(self, document_id: UUID, status: DocumentStatus) -> None:
        async with self._session_factory() as session, session.begin():
            await self._documents(session).set_status(document_id, status)

    async def _fail(self, document_id: UUID, code: DocumentErrorCode, detail: str) -> None:
        async with self._session_factory() as session, session.begin():
            await self._documents(session).set_status(
                document_id, DocumentStatus.FAILED, error_code=code, error_detail=detail
            )
        await self._notifier.emit(
            document_id, ProgressEventType.ERROR, stage="parsing", message="Document parsing failed"
        )

    async def _update_source(self, document_id: UUID, key: str, title: str | None) -> None:
        async with self._session_factory() as session, session.begin():
            await self._documents(session).update_source(document_id, object_key=key, title=title)

    async def _update_page_count(self, document_id: UUID, page_count: int | None) -> None:
        if page_count is None:
            return
        async with self._session_factory() as session, session.begin():
            document = await self._documents(session).get(document_id)
            if document is not None:
                await self._documents(session).update_source(
                    document_id, object_key=document.object_key, page_count=page_count
                )


class IngestFailure(Exception):
    def __init__(self, code: DocumentErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _walk(nodes: list[TopicNode]) -> Iterator[TopicNode]:
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _has_heading(markdown: str) -> bool:
    return any(line.startswith("#") and len(line) > 1 and line[1] in "# " for line in markdown.splitlines())


def _normalize_images(parsed: ParsedDocument) -> ParsedDocument:
    """Remove unusable/repeated images before offsets and tree are calculated."""
    import hashlib
    from io import BytesIO

    from PIL import Image

    kept: list[ExtractedImage] = []
    markdown = parsed.markdown
    seen: set[str] = set()
    for image in parsed.images:
        try:
            value = Image.open(BytesIO(image.data)).convert("RGBA")
            digest = hashlib.sha256(value.tobytes()).hexdigest()
            if value.width < 48 or value.height < 48 or digest in seen:
                markdown = markdown.replace(f'\n::image{{id="{image.ref}"}}\n', "\n", 1)
                continue
            seen.add(digest)
            kept.append(image)
        except Exception:
            markdown = markdown.replace(f'\n::image{{id="{image.ref}"}}\n', "\n", 1)
    return ParsedDocument(markdown, tuple(kept), parsed.page_count, parsed.title, parsed.heading_pages)
