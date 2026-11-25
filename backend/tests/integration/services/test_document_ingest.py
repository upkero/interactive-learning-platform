"""Exercise ingestion against PostgreSQL with isolated in-memory object storage."""

import asyncio
import base64
import json
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import DocumentErrorCode, DocumentStatus, SourceType
from src.app.contracts.documents.topic_node import TopicNode
from src.app.contracts.ingest import ExtractedImage, ParsedDocument
from src.app.db.parsing_lease import PostgresParsingLease
from src.app.exceptions.ingest import GDocsImportError
from src.app.ingest.parsers.base import DocumentParser, ParserRegistry
from src.app.ingest.parsers.docling_parser import DoclingParser
from src.app.ingest.parsers.gdocs_importer import GDocsImporter
from src.app.ingest.parsers.markdown_parser import MarkdownParser
from src.app.interfaces.storage.object_storage_client import StorageBucket
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.documents.document_ingest_service import DocumentIngestService
from src.app.storage.object_keys import parsed_markdown_key
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_docx_parsed_and_repeated_delivery_does_not_overwrite(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    data = (Path(__file__).parents[2] / "fixtures/documents/headings.docx").read_bytes()
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Test",
            source_type=SourceType.UPLOAD,
            object_key="headings.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=len(data),
            checksum="a" * 64,
        )
    storage = FakeObjectStorageClient(objects={("documents", "headings.docx"): data})
    notifier = FakeProgressNotifier()
    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((DoclingParser(), MarkdownParser())),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        notifier=notifier,
    )
    await service.parse(document.id)
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
    assert result is not None and result.status is DocumentStatus.PARSED
    assert result.topic_tree and result.topic_tree[0].title == "Introduction"
    assert result.topic_tree[0].children[0].title == "Details"
    assert await storage.get_object(bucket="documents", key=parsed_markdown_key(user.id, document.id))
    assert any(event[3] == "parsing" for event in notifier.events)
    count = len(storage.put_object_calls)
    await service.parse(document.id)
    assert len(storage.put_object_calls) == count


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_delivery_does_not_replace_active_parse(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowStorage(FakeObjectStorageClient):
        async def get_object(self, *, bucket: StorageBucket, key: str) -> bytes:
            entered.set()
            await release.wait()
            return await super().get_object(bucket=bucket, key=key)

    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Race",
            source_type=SourceType.UPLOAD,
            object_key="race.md",
            mime_type="text/markdown",
            size_bytes=11,
            checksum="a" * 64,
        )
    storage = SlowStorage(objects={("documents", "race.md"): b"# One\nText"})
    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((MarkdownParser(),)),
        notifier=FakeProgressNotifier(),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
    )
    first = asyncio.create_task(service.parse(document.id))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await asyncio.wait_for(service.parse(document.id), 5)
    finally:
        release.set()
        await first
    assert storage.get_object_calls == [("documents", "race.md")]
    assert len(storage.put_object_calls) == 1
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
    assert result is not None and result.status is DocumentStatus.PARSED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_image_refs_match_database_after_filtering(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    def image(size: int, color: str) -> str:
        output = BytesIO()
        Image.new("RGB", (size, size), color).save(output, format="PNG")
        return base64.b64encode(output.getvalue()).decode()

    red = image(100, "red")
    source = (
        "# Images\n\n"
        + "\n\n".join(
            f"![picture](data:image/png;base64,{value})" for value in (red, image(20, "blue"), image(120, "green"), red)
        )
    ).encode()
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Images",
            source_type=SourceType.UPLOAD,
            object_key="images.md",
            mime_type="text/markdown",
            size_bytes=len(source),
            checksum="b" * 64,
        )
    storage = FakeObjectStorageClient(objects={("documents", "images.md"): source})

    class FailedVision:
        async def describe(
            self, images: tuple[ExtractedImage, ...], *, document_context: str = ""
        ) -> dict[str, str | None]:
            raise RuntimeError("vision unavailable")

    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((MarkdownParser(),)),
        notifier=FakeProgressNotifier(),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        image_describer=FailedVision(),
    )
    await service.parse(document.id)
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
        images = await ImageRepository(session).list_by_document(document.id)
    assert result is not None and result.status is DocumentStatus.PARSED
    markdown = (await storage.get_object(bucket="documents", key=parsed_markdown_key(user.id, document.id))).decode()
    assert '::image{id="img_1"}' in markdown and '::image{id="img_3"}' in markdown
    assert '::image{id="img_2"}' not in markdown and '::image{id="img_4"}' not in markdown
    assert {item.object_key for item in images} == {f"{document.id}/img_1.png", f"{document.id}/img_3.png"}
    assert all(item.topic_id == "1" and item.width and item.height for item in images)
    assert all(item.description is None for item in images)
    assert {key for bucket, key, _, _ in storage.put_object_calls if bucket == "images"} == {
        item.object_key for item in images
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_segmentation_failure_keeps_document_parsed(
    session_factory: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    class BrokenSegmenter:
        async def segment(self, markdown: str) -> str:
            raise RuntimeError("unavailable")

    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Text",
            source_type=SourceType.UPLOAD,
            object_key="text.md",
            mime_type="text/markdown",
            size_bytes=5,
            checksum="c" * 64,
        )
    storage = FakeObjectStorageClient(objects={("documents", "text.md"): b"Plain text."})
    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((MarkdownParser(),)),
        notifier=FakeProgressNotifier(),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        topic_segmenter=BrokenSegmenter(),
    )
    await service.parse(document.id)
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
    assert result is not None and result.status is DocumentStatus.PARSED
    assert result.topic_tree and len(result.topic_tree) == 1
    assert any(
        record.name == "grasp.decisions" and getattr(record, "event", None) == "ingest.segmentation_skipped"
        for record in caplog.records
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["empty", "pages", "private"])
async def test_known_ingest_errors(session_factory: async_sessionmaker[AsyncSession], scenario: str) -> None:
    class TestParser(DocumentParser):
        supported_mime_types = frozenset({"text/plain"})

        def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
            return ParsedDocument(
                markdown="" if scenario == "empty" else "Text", page_count=301 if scenario == "pages" else 1
            )

    class PrivateDocs:
        async def fetch(self, url: str) -> tuple[bytes, str | None]:
            raise GDocsImportError(DocumentErrorCode.GDOCS_NOT_PUBLIC, "Private")

    source_type = SourceType.GDOCS if scenario == "private" else SourceType.UPLOAD
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Test",
            source_type=source_type,
            source_uri="https://docs.google.com/document/d/abc/edit",
            object_key="test.txt",
            mime_type="text/plain",
            size_bytes=1,
            checksum="d" * 64,
        )
    storage = FakeObjectStorageClient(objects={("documents", "test.txt"): b"x"})
    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((TestParser(),)),
        notifier=FakeProgressNotifier(),
        gdocs=PrivateDocs(),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
    )
    await service.parse(document.id)
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
    assert result is not None and result.status is DocumentStatus.FAILED
    assert (
        result.error_code
        is {
            "empty": DocumentErrorCode.EMPTY_DOCUMENT,
            "pages": DocumentErrorCode.TOO_MANY_PAGES,
            "private": DocumentErrorCode.GDOCS_NOT_PUBLIC,
        }[scenario]
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.timeout(240)
async def test_pdf_parses_to_tree_and_images(session_factory: async_sessionmaker[AsyncSession]) -> None:
    fixture = Path(__file__).parents[2] / "fixtures/documents/textbook_en.pdf"
    data = fixture.read_bytes()
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="PDF",
            source_type=SourceType.UPLOAD,
            object_key="textbook.pdf",
            mime_type="application/pdf",
            size_bytes=len(data),
            checksum="e" * 64,
        )
    storage = FakeObjectStorageClient(objects={("documents", "textbook.pdf"): data})
    described_ref: str | None = None

    class PDFVision:
        async def describe(
            self, images: tuple[ExtractedImage, ...], *, document_context: str = ""
        ) -> dict[str, str | None]:
            nonlocal described_ref
            assert images and all(image.media_type == "image/png" for image in images)
            assert all(f'::image{{id="{image.ref}"}}' in document_context for image in images)
            described_ref = images[0].ref
            return {
                image.ref: "Diagram of the learning process" if image.ref == described_ref else None for image in images
            }

    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((DoclingParser(),)),
        notifier=FakeProgressNotifier(),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        image_describer=PDFVision(),
    )
    await service.parse(document.id)
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
        images = await ImageRepository(session).list_by_document(document.id)
    assert result is not None and result.status is DocumentStatus.PARSED
    assert result.page_count == 3 and result.topic_tree
    markdown = (await storage.get_object(bucket="documents", key=parsed_markdown_key(user.id, document.id))).decode()
    refs = set(re.findall(r'::image\{id="(img_\d+)"\}', markdown))
    assert refs
    assert refs == {image.object_key.rsplit("/", 1)[-1].removesuffix(".png") for image in images}
    assert all(image.page is not None and image.width and image.height and image.topic_id for image in images)
    assert described_ref is not None
    assert next(image.description for image in images if image.object_key.endswith(f"/{described_ref}.png")) == (
        "Diagram of the learning process"
    )
    assert all(image.description is None for image in images if not image.object_key.endswith(f"/{described_ref}.png"))

    def check(node: TopicNode) -> None:
        assert node.total_tokens == node.own_tokens + sum(child.total_tokens for child in node.children)
        for child in node.children:
            check(child)

    for root in result.topic_tree:
        check(root)
    assert result.topic_tree[0].start == 0 and result.topic_tree[-1].end == len(markdown)
    golden = json.loads((fixture.parent / "textbook_en.tree.json").read_text(encoding="utf-8"))

    def titles(nodes: tuple[TopicNode, ...]) -> list[dict[str, object]]:
        return [
            {
                "id": node.id,
                "title": node.title,
                "level": node.level,
                "page": node.page,
                "children": titles(node.children),
            }
            for node in nodes
        ]

    assert titles(result.topic_tree) == golden
