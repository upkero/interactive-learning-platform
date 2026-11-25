"""Exercise ingestion against PostgreSQL with isolated in-memory object storage."""

import asyncio
import base64
import json
import os
import re
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from PIL import Image
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import DocumentErrorCode, DocumentStatus, SourceType
from src.app.contracts.documents.topic_node import TopicNode
from src.app.contracts.ingest import ExtractedImage, ParsedDocument
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.progress.stream import stream_key
from src.app.core.settings.ingest import IngestSettings
from src.app.core.settings.progress import ProgressSettings
from src.app.core.settings.upload import UploadSettings
from src.app.db.parsing_lease import PostgresParsingLease
from src.app.exceptions.ingest import GDocsImportError
from src.app.ingest.images import ImageStore
from src.app.ingest.parsers.base import DocumentParser, ParserRegistry
from src.app.ingest.parsers.docling_parser import DoclingParser
from src.app.ingest.parsers.gdocs_importer import GDocsImporter
from src.app.ingest.parsers.markdown_parser import MarkdownParser
from src.app.ingest.tokens import TokenCounter
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.interfaces.services.ingest import ImageDescriberProtocol
from src.app.interfaces.storage.object_storage_client import StorageBucket
from src.app.observability.progress_notifier import RedisProgressNotifier
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.documents.document_ingest_runner import DocumentIngestRunner
from src.app.services.documents.document_ingest_service import DocumentIngestService
from src.app.services.documents.file_inspector import FileInspector
from src.app.services.documents.topic_segmenter import Section, Sections, TopicSegmenter
from src.app.storage.object_keys import parsed_markdown_key
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient
from tests.support.fixtures.documents import docx_bomb_bytes


def _png_data_url(size: int, color: str) -> str:
    output = BytesIO()
    Image.new("RGB", (size, size), color).save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


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
        registry=ParserRegistry(
            (DoclingParser(artifacts_path=IngestSettings().docling_artifacts_path), MarkdownParser())
        ),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        image_store=ImageStore(storage),
        inspector=FileInspector(UploadSettings()),
        counter=TokenCounter(),
        ingest_settings=IngestSettings(),
        upload_settings=UploadSettings(),
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
        image_store=ImageStore(storage),
        inspector=FileInspector(UploadSettings()),
        counter=TokenCounter(),
        ingest_settings=IngestSettings(),
        upload_settings=UploadSettings(),
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
    red = _png_data_url(100, "red")
    source = (
        "# Images\n\n"
        + "\n\n".join(
            f"![picture]({value})" for value in (red, _png_data_url(20, "blue"), _png_data_url(120, "green"), red)
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
            self,
            images: tuple[ExtractedImage, ...],
            *,
            document_context: str = "",
            topic_titles: dict[str, str] | None = None,
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
        image_store=ImageStore(storage),
        inspector=FileInspector(UploadSettings()),
        counter=TokenCounter(),
        ingest_settings=IngestSettings(),
        upload_settings=UploadSettings(),
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
@pytest.mark.parametrize("layout", ["inline", "table", "long-inline", "empty-alt-line"])
async def test_segmentation_keeps_images_in_their_source_topic(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    pictures = f"![diagram]({_png_data_url(64, 'red')}) ![detail]({_png_data_url(80, 'blue')})"
    tiny = _png_data_url(8, "white")
    content = f"Paragraph about a diagram {pictures} ![tiny]({tiny})."
    if layout == "table":
        content = f"Caption | Pictures\n--- | ---\nProcess | {pictures} ![tiny]({tiny})"
    if layout == "long-inline":
        content += " " + "word " * 30000 + "end."
    source = f"{content}\n\nAnother subject.\n".encode()
    if layout == "empty-alt-line":
        source = f"Paragraph about a diagram {pictures}.\n![]({tiny})\nAnother subject.\n".encode()
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Topics",
            source_type=SourceType.UPLOAD,
            object_key="topics.md",
            mime_type="text/markdown",
            size_bytes=len(source),
            checksum="a" * 64,
        )
    storage = FakeObjectStorageClient(objects={("documents", "topics.md"): source})
    vision = AsyncMock(spec=ImageDescriberProtocol)
    vision.describe.return_value = {}
    counter = TokenCounter()
    model_inputs: list[str] = []

    async def suggest(llm: LLMClient, request: LLMRequest, schema: type[Sections]) -> Sections:
        markdown = request.messages[0].content
        assert isinstance(markdown, str)
        model_inputs.append(markdown)
        sections = []
        for match in re.finditer(r"\[p(\d+)\] (\S+)", markdown):
            number = int(match[1])
            title = "Diagrams" if number == 1 else "Other" if match[2] == "Another" else f"Text {number}"
            sections.append(Section(title=title, first_paragraph=number))
        return Sections(sections=sections)

    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", suggest)
    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((MarkdownParser(),)),
        notifier=FakeProgressNotifier(),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        image_store=ImageStore(storage),
        inspector=FileInspector(UploadSettings()),
        counter=counter,
        ingest_settings=IngestSettings(),
        upload_settings=UploadSettings(),
        topic_segmenter=TopicSegmenter(AsyncMock(spec=LLMClient), counter=counter),
        image_describer=vision,
    )
    await service.parse(document.id)

    assert model_inputs
    assert all('::image{id="img_3"}' not in model_input for model_input in model_inputs)
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
        images = await ImageRepository(session).list_by_document(document.id)
    assert result is not None and result.status is DocumentStatus.PARSED
    assert result.topic_tree is not None
    first, last = result.topic_tree[0], result.topic_tree[-1]
    if layout == "long-inline":
        assert len(model_inputs) > 1 and len(result.topic_tree) > 2
    else:
        assert len(model_inputs) == 1 and len(result.topic_tree) == 2
    assert (first.title, first.image_ids) == ("Diagrams", ("img_1", "img_2"))
    assert (last.title, last.image_ids) == ("Other", ())
    assert all(not topic.image_ids for topic in result.topic_tree[1:])
    assert len(images) == 2 and all(image.topic_id == first.id for image in images)
    saved_markdown = (
        await storage.get_object(bucket="documents", key=parsed_markdown_key(user.id, document.id))
    ).decode()
    assert saved_markdown[last.start : last.end].startswith("## Other\n\nAnother subject.")
    vision.describe.assert_awaited_once()
    assert vision.describe.await_args.kwargs["topic_titles"] == {"img_1": "Diagrams", "img_2": "Diagrams"}


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("oversized_table", [False, True])
async def test_segmentation_failure_keeps_document_parsed(
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
    oversized_table: bool,
) -> None:
    class BrokenSegmenter:
        async def segment(self, markdown: str, *, image_spans: Mapping[str, tuple[int, int]] | None = None) -> str:
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
    source = "Col A | Col B\n--- | ---\n" + "a | b\n" * 6000 if oversized_table else "Plain text."
    storage = FakeObjectStorageClient(objects={("documents", "text.md"): source.encode()})
    counter = TokenCounter()
    llm = AsyncMock(spec=LLMClient)
    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((MarkdownParser(),)),
        notifier=FakeProgressNotifier(),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        image_store=ImageStore(storage),
        inspector=FileInspector(UploadSettings()),
        counter=counter,
        ingest_settings=IngestSettings(),
        upload_settings=UploadSettings(),
        topic_segmenter=TopicSegmenter(llm, counter=counter) if oversized_table else BrokenSegmenter(),
    )
    await service.parse(document.id)
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
    assert result is not None and result.status is DocumentStatus.PARSED
    assert result.topic_tree and len(result.topic_tree) == 1
    assert (
        await storage.get_object(bucket="documents", key=parsed_markdown_key(user.id, document.id)) == source.encode()
    )
    assert not llm.mock_calls
    assert any(
        record.name == "grasp.decisions" and getattr(record, "event", None) == "ingest.segmentation_skipped"
        for record in caplog.records
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["empty", "filtered_image", "pages", "private", "parser"])
async def test_known_ingest_errors(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    class TestParser(DocumentParser):
        supported_mime_types = frozenset({"text/plain"})

        def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
            if scenario == "parser":
                raise RuntimeError("internal parser detail")
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
    source = f"![tiny]({_png_data_url(8, 'white')})".encode() if scenario == "filtered_image" else b"x"
    storage = FakeObjectStorageClient(objects={("documents", "test.txt"): source})
    notifier = FakeProgressNotifier()
    segment = AsyncMock(return_value=Sections(sections=[]))
    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", segment)
    counter = TokenCounter()
    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((MarkdownParser(),) if scenario == "filtered_image" else (TestParser(),)),
        notifier=notifier,
        gdocs=PrivateDocs(),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        image_store=ImageStore(storage),
        inspector=FileInspector(UploadSettings()),
        counter=counter,
        ingest_settings=IngestSettings(),
        upload_settings=UploadSettings(),
        topic_segmenter=TopicSegmenter(AsyncMock(spec=LLMClient), counter=counter),
    )
    await service.parse(document.id)
    async with session_factory() as session:
        result = await DocumentRepository(session).get(document.id)
    assert result is not None and result.status is DocumentStatus.FAILED
    assert (
        result.error_code
        is {
            "empty": DocumentErrorCode.EMPTY_DOCUMENT,
            "filtered_image": DocumentErrorCode.EMPTY_DOCUMENT,
            "pages": DocumentErrorCode.TOO_MANY_PAGES,
            "private": DocumentErrorCode.GDOCS_NOT_PUBLIC,
            "parser": DocumentErrorCode.PARSE_FAILED,
        }[scenario]
    )
    assert notifier.error_codes[-1] is result.error_code
    assert not storage.put_object_calls
    segment.assert_not_awaited()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["login", "empty", "invalid", "pdf", "oversized", "bomb"])
async def test_gdocs_export_validation_before_storage_and_public_code(
    session_factory: async_sessionmaker[AsyncSession], scenario: str
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if scenario == "login":
            return httpx.Response(302, headers={"location": "https://accounts.google.com/ServiceLogin"})
        if scenario == "pdf":
            pdf = (Path(__file__).parents[2] / "fixtures/documents/textbook_en.pdf").read_bytes()
            return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})
        content = {
            "empty": b"",
            "invalid": b"not a docx",
            "oversized": b"x" * 1025,
            "bomb": docx_bomb_bytes(1001),
        }[scenario]
        return httpx.Response(200, content=content)

    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Google Docs",
            source_type=SourceType.GDOCS,
            source_uri="https://docs.google.com/document/d/abc123/edit",
            object_key="",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=0,
            checksum="d" * 64,
        )
    storage = FakeObjectStorageClient()
    notifier = FakeProgressNotifier()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        service = DocumentIngestService(
            session_factory=session_factory,
            documents=DocumentRepository,
            images=ImageRepository,
            storage=storage,
            registry=ParserRegistry((MarkdownParser(),)),
            notifier=notifier,
            gdocs=GDocsImporter(
                max_bytes=UploadSettings().max_bytes if scenario == "pdf" else 10240 if scenario == "bomb" else 1024,
                client=client,
            ),
            parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
            image_store=ImageStore(storage),
            inspector=FileInspector(UploadSettings(max_unzipped_bytes=1000)),
            counter=TokenCounter(),
            ingest_settings=IngestSettings(),
            upload_settings=UploadSettings(),
        )
        await service.parse(document.id)
    async with session_factory() as session:
        saved = await DocumentRepository(session).get(document.id)
    assert saved is not None and saved.status is DocumentStatus.FAILED
    expected = DocumentErrorCode.GDOCS_NOT_PUBLIC if scenario == "login" else DocumentErrorCode.GDOCS_IMPORT_FAILED
    assert saved.error_code is expected and notifier.error_codes[-1] is expected
    assert not storage.put_object_calls


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("private", [False, True])
async def test_error_code_in_real_redis_stream_matches_database(
    session_factory: async_sessionmaker[AsyncSession], private: bool
) -> None:
    url = os.environ.get("REDIS_PROGRESS_URL")
    if not url:
        pytest.skip("REDIS_PROGRESS_URL must point to an isolated Redis database")
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Progress error",
            source_type=SourceType.GDOCS if private else SourceType.UPLOAD,
            source_uri="https://docs.google.com/document/d/abc123/edit" if private else None,
            object_key="test.txt",
            mime_type="text/plain",
            size_bytes=1,
            checksum="d" * 64,
        )

    class BrokenParser(DocumentParser):
        supported_mime_types = frozenset({"text/plain"})

        def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
            raise RuntimeError("internal diagnostics")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(302, headers={"location": "https://accounts.google.com/ServiceLogin"})
        )
    ) as client:
        redis = Redis.from_url(url)
        try:
            storage = FakeObjectStorageClient(objects={("documents", "test.txt"): b"x"})
            service = DocumentIngestService(
                session_factory=session_factory,
                documents=DocumentRepository,
                images=ImageRepository,
                storage=storage,
                registry=ParserRegistry((BrokenParser(),)),
                notifier=RedisProgressNotifier(redis, ProgressSettings()),
                gdocs=GDocsImporter(max_bytes=1024, client=client),
                parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
                image_store=ImageStore(storage),
                inspector=FileInspector(UploadSettings()),
                counter=TokenCounter(),
                ingest_settings=IngestSettings(),
                upload_settings=UploadSettings(),
            )
            await service.parse(document.id)
            entries = await redis.xrange(stream_key(document.id))
        finally:
            await redis.delete(stream_key(document.id))
            await redis.aclose()
    async with session_factory() as session:
        saved = await DocumentRepository(session).get(document.id)
    assert saved is not None and saved.error_code is not None
    payload = json.loads(entries[-1][1][b"data"])
    assert payload["type"] == "error" and payload["error_code"] == saved.error_code.value
    assert "internal diagnostics" not in payload["message"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialization_failure_uses_lease_and_emits_code(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=user.id,
            title="Init failure",
            source_type=SourceType.UPLOAD,
            object_key="test.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="f" * 64,
        )
    notifier = FakeProgressNotifier()

    def broken() -> DocumentIngestService:
        raise RuntimeError("broken dependency")

    lease = PostgresParsingLease(session_factory.kw["bind"])
    runner = DocumentIngestRunner(
        lease=lease, build=broken, session_factory=session_factory, documents=DocumentRepository, notifier=notifier
    )
    async with lease.acquire(document.id) as acquired:
        assert acquired
        await runner.parse(document.id)
    async with session_factory() as session:
        untouched = await DocumentRepository(session).get(document.id)
    assert untouched is not None and untouched.status is DocumentStatus.UPLOADED
    await runner.parse(document.id)
    async with session_factory() as session:
        failed = await DocumentRepository(session).get(document.id)
    assert failed is not None and failed.status is DocumentStatus.FAILED
    assert failed.error_code is DocumentErrorCode.PARSE_FAILED
    assert notifier.error_codes == [DocumentErrorCode.PARSE_FAILED]


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
            self,
            images: tuple[ExtractedImage, ...],
            *,
            document_context: str = "",
            topic_titles: dict[str, str] | None = None,
        ) -> dict[str, str | None]:
            nonlocal described_ref
            assert images and all(image.media_type == "image/png" for image in images)
            assert all(f'::image{{id="{image.ref}"}}' in document_context for image in images)
            assert topic_titles is not None and all(topic_titles[image.ref] for image in images)
            described_ref = images[0].ref
            return {
                image.ref: "Diagram of the learning process" if image.ref == described_ref else None for image in images
            }

    service = DocumentIngestService(
        session_factory=session_factory,
        documents=DocumentRepository,
        images=ImageRepository,
        storage=storage,
        registry=ParserRegistry((DoclingParser(artifacts_path=IngestSettings().docling_artifacts_path),)),
        notifier=FakeProgressNotifier(),
        gdocs=GDocsImporter(max_bytes=1024),
        parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
        image_store=ImageStore(storage),
        inspector=FileInspector(UploadSettings()),
        counter=TokenCounter(),
        ingest_settings=IngestSettings(),
        upload_settings=UploadSettings(),
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
