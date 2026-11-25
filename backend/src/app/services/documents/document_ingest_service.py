import logging
from collections.abc import Callable, Iterator
from functools import partial
from uuid import UUID

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.statuses import DocumentErrorCode, DocumentStatus, SourceType
from src.app.contracts.documents.topic_node import TopicNode
from src.app.contracts.ingest import ParsedDocument
from src.app.contracts.progress.event_type import ProgressEventType
from src.app.core.settings.ingest import get_ingest_settings
from src.app.core.settings.upload import get_upload_settings
from src.app.exceptions.ingest import GDocsImportError, IngestFailure
from src.app.ingest.images import ImageStore
from src.app.ingest.tokens import get_token_counter
from src.app.ingest.topic_tree import _inside_code_fence, build_topic_tree
from src.app.interfaces.repositories.documents import DocumentRepositoryProtocol, ImageRepositoryProtocol
from src.app.interfaces.services.ingest import (
    GoogleDocsImporter,
    ImageDescriberProtocol,
    ParserResolver,
    ParsingLease,
    TopicSegmenterProtocol,
)
from src.app.interfaces.services.progress_notifier import ProgressNotifier
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.services.documents.document_failure import mark_document_failed
from src.app.storage.object_keys import parsed_markdown_key, source_key

logger = logging.getLogger(__name__)


class DocumentIngestService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        images: Callable[[AsyncSession], ImageRepositoryProtocol],
        storage: ObjectStorageClient,
        registry: ParserResolver,
        notifier: ProgressNotifier,
        gdocs: GoogleDocsImporter,
        parsing_lease: ParsingLease,
        image_describer: ImageDescriberProtocol | None = None,
        topic_segmenter: TopicSegmenterProtocol | None = None,
    ) -> None:
        self._session_factory, self._documents, self._images = session_factory, documents, images
        self._storage, self._registry, self._notifier = storage, registry, notifier
        self._gdocs = gdocs
        self._parsing_lease = parsing_lease
        self._image_describer = image_describer
        self._topic_segmenter = topic_segmenter

    async def parse(self, document_id: UUID) -> None:
        async with self._parsing_lease.acquire(document_id) as acquired:
            if not acquired:
                logger.info("Document is already being parsed", extra={"document_id": str(document_id)})
                return
            await self._parse_locked(document_id)

    async def _parse_locked(self, document_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            document = await self._documents(session).begin_parsing(document_id)
        if document is None:
            logger.info("Document is not eligible for parsing", extra={"document_id": str(document_id)})
            return
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
                await self._update_source(document_id, source, title, len(data))
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
            initial_tree = build_topic_tree(parsed.markdown, get_token_counter(), parsed.heading_pages)
            segment_needed = not _has_heading(parsed.markdown) or (
                len(initial_tree) == 1
                and not initial_tree[0].children
                and initial_tree[0].total_tokens > get_ingest_settings().segment_max_tokens
            )
            if self._topic_segmenter is not None and segment_needed:
                try:
                    segmented = await self._topic_segmenter.segment(parsed.markdown)
                except Exception as exc:
                    logger.warning("Topic segmentation skipped", extra={"document_id": str(document_id)}, exc_info=True)
                    logging.getLogger("grasp.decisions").warning(
                        "Topic segmentation skipped",
                        extra={"event": "ingest.segmentation_skipped", "reason": type(exc).__name__},
                    )
                else:
                    parsed = ParsedDocument(
                        markdown=segmented,
                        images=parsed.images,
                        page_count=parsed.page_count,
                        title=parsed.title,
                        heading_pages=parsed.heading_pages,
                    )
            await self._store_result(document, parsed)
        except GDocsImportError as exc:
            await self._fail(document_id, exc.code, str(exc))
        except IngestFailure as exc:
            await self._fail(document_id, exc.code, str(exc))
        except Exception as exc:
            logger.exception("Document parsing failed", extra={"document_id": str(document_id)})
            await self._fail(document_id, DocumentErrorCode.PARSE_FAILED, repr(exc))

    async def _store_result(self, document: DocumentRecord, parsed: ParsedDocument) -> None:
        document_id = document.id
        markdown, saved = await ImageStore(self._storage).save(document_id, parsed.markdown, parsed.images)
        tree = build_topic_tree(markdown, get_token_counter(), parsed.heading_pages)
        await self._storage.put_object(
            bucket="documents",
            key=parsed_markdown_key(document.owner_id, document_id),
            data=markdown.encode(),
            content_type="text/markdown; charset=utf-8",
        )
        await self._notifier.emit(document_id, ProgressEventType.STAGE, stage="images", message="Images extracted")
        descriptions: dict[str, str | None] = {}
        if self._image_describer is not None and saved:
            try:
                descriptions = await self._image_describer.describe(
                    tuple(item.image for item in saved), document_context=markdown
                )
            except Exception:
                logger.warning(
                    "Image descriptions were not generated", extra={"document_id": str(document_id)}, exc_info=True
                )
        drafts = [
            ImageDraft(
                object_key=item.key,
                width=item.width,
                height=item.height,
                page=item.image.page,
                caption=item.image.caption,
                topic_id=next((node.id for node in _walk(tree) if item.image.ref in node.image_ids), None),
            )
            for item in saved
        ]
        async with self._session_factory() as session, session.begin():
            await self._images(session).delete_by_document(document_id)
            await self._images(session).add_many(document_id, drafts)
            await self._images(session).update_descriptions(document_id, descriptions)
            await self._documents(session).set_topic_tree(document_id, [node.to_dict() for node in tree])
            key = (
                source_key(document.owner_id, document.id, "docx")
                if document.source_type is SourceType.GDOCS
                else document.object_key
            )
            await self._documents(session).update_source(document_id, object_key=key, page_count=parsed.page_count)
            await self._documents(session).set_status(document_id, DocumentStatus.PARSED)

    async def _fail(self, document_id: UUID, code: DocumentErrorCode, detail: str) -> None:
        await mark_document_failed(
            session_factory=self._session_factory,
            documents=self._documents,
            document_id=document_id,
            error_code=code,
            error_detail=detail,
        )
        await self._notifier.emit(
            document_id, ProgressEventType.ERROR, stage="parsing", message="Document parsing failed"
        )

    async def _update_source(self, document_id: UUID, key: str, title: str | None, size_bytes: int) -> None:
        async with self._session_factory() as session, session.begin():
            await self._documents(session).update_source(
                document_id,
                object_key=key,
                title=title,
                size_bytes=size_bytes,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )


def _walk(nodes: list[TopicNode] | tuple[TopicNode, ...]) -> Iterator[TopicNode]:
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _has_heading(markdown: str) -> bool:
    import re

    return any(
        not _inside_code_fence(markdown, match.start())
        for match in re.finditer(r"^#{1,3}\s+\S", markdown, re.MULTILINE)
    )
