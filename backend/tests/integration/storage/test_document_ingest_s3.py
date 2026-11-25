"""Ingestion with real PostgreSQL and MinIO; each test owns its object keys."""

import base64
import json
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import DocumentStatus, SourceType
from src.app.contracts.documents.topic_node import TopicNode
from src.app.core.settings.ingest import IngestSettings
from src.app.core.settings.upload import UploadSettings
from src.app.db.parsing_lease import PostgresParsingLease
from src.app.exceptions.storage import ObjectNotFoundError
from src.app.ingest.images import ImageStore
from src.app.ingest.parsers.base import ParserRegistry
from src.app.ingest.parsers.docling_parser import DoclingParser
from src.app.ingest.parsers.gdocs_importer import GDocsImporter
from src.app.ingest.parsers.markdown_parser import MarkdownParser
from src.app.ingest.tokens import TokenCounter
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.documents.document_ingest_service import DocumentIngestService
from src.app.services.documents.file_inspector import FileInspector
from src.app.storage.object_keys import parsed_markdown_key
from src.app.storage.s3_object_storage_client import S3ObjectStorageClient
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_images_match_s3_and_database(
    object_storage: S3ObjectStorageClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    def png(size: int, color: str) -> str:
        output = BytesIO()
        Image.new("RGB", (size, size), color).save(output, "PNG")
        return base64.b64encode(output.getvalue()).decode()

    red = png(100, "red")
    source = (
        "# Topic\n\n"
        + "\n\n".join(
            f"![image](data:image/png;base64,{value})" for value in (red, png(20, "blue"), png(120, "green"), red)
        )
    ).encode()
    document_id = uuid4()
    key = f"tests/ingest/{document_id}/source.md"
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            id=document_id,
            owner_id=user.id,
            title="S3",
            source_type=SourceType.UPLOAD,
            object_key=key,
            mime_type="text/markdown",
            size_bytes=len(source),
            checksum="f" * 64,
        )
    parsed_key = parsed_markdown_key(user.id, document.id)
    try:
        await object_storage.put_object(bucket="documents", key=key, data=source, content_type="text/markdown")
        service = DocumentIngestService(
            session_factory=session_factory,
            documents=DocumentRepository,
            images=ImageRepository,
            storage=object_storage,
            registry=ParserRegistry((MarkdownParser(),)),
            notifier=FakeProgressNotifier(),
            gdocs=GDocsImporter(max_bytes=1024),
            parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
            image_store=ImageStore(object_storage),
            inspector=FileInspector(UploadSettings()),
            counter=TokenCounter(),
            ingest_settings=IngestSettings(),
            upload_settings=UploadSettings(),
        )
        await service.parse(document.id)
        async with session_factory() as session:
            result = await DocumentRepository(session).get(document.id)
            images = await ImageRepository(session).list_by_document(document.id)
        assert result is not None and result.status is DocumentStatus.PARSED
        markdown = (await object_storage.get_object(bucket="documents", key=parsed_key)).decode()
        refs = set(re.findall(r'::image\{id="(img_\d+)"\}', markdown))
        assert refs == {"img_1", "img_3"}
        assert {image.object_key for image in images} == {f"{document.id}/{ref}.png" for ref in refs}
        for image in images:
            assert await object_storage.get_object(bucket="images", key=image.object_key)
        for ref in ("img_2", "img_4"):
            with pytest.raises(ObjectNotFoundError):
                await object_storage.get_object(bucket="images", key=f"{document.id}/{ref}.png")
    finally:
        await object_storage.delete_prefix(bucket="images", prefix=f"{document.id}/")
        await object_storage.delete_object(bucket="documents", key=key)
        await object_storage.delete_object(bucket="documents", key=parsed_key)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.timeout(240)
async def test_pdf_parses_and_retry_cleans_orphaned_s3_images(
    object_storage: S3ObjectStorageClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fixture = Path(__file__).parents[2] / "fixtures/documents/textbook_en.pdf"
    data = fixture.read_bytes()
    document_id = uuid4()
    key = f"tests/ingest/{document_id}/source.pdf"
    async with session_factory() as session, session.begin():
        user = await UserRepository(session).create(email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20)
        document = await DocumentRepository(session).create(
            id=document_id,
            owner_id=user.id,
            title="PDF",
            source_type=SourceType.UPLOAD,
            object_key=key,
            mime_type="application/pdf",
            size_bytes=len(data),
            checksum="e" * 64,
        )
    parsed_key = parsed_markdown_key(user.id, document.id)
    orphan = f"{document.id}/img_99.png"
    try:
        await object_storage.put_object(bucket="documents", key=key, data=data, content_type="application/pdf")
        service = DocumentIngestService(
            session_factory=session_factory,
            documents=DocumentRepository,
            images=ImageRepository,
            storage=object_storage,
            registry=ParserRegistry((DoclingParser(artifacts_path=IngestSettings().docling_artifacts_path),)),
            notifier=FakeProgressNotifier(),
            gdocs=GDocsImporter(max_bytes=1024),
            parsing_lease=PostgresParsingLease(session_factory.kw["bind"]),
            image_store=ImageStore(object_storage),
            inspector=FileInspector(UploadSettings()),
            counter=TokenCounter(),
            ingest_settings=IngestSettings(),
            upload_settings=UploadSettings(),
        )
        await service.parse(document.id)
        async with session_factory() as session:
            result = await DocumentRepository(session).get(document.id)
            images = await ImageRepository(session).list_by_document(document.id)
        assert result is not None and result.status is DocumentStatus.PARSED and result.page_count == 3
        expected = json.loads((fixture.parent / "textbook_en.tree.json").read_text(encoding="utf-8"))

        def tree(nodes: tuple[TopicNode, ...]) -> list[dict[str, object]]:
            return [
                {"id": n.id, "title": n.title, "level": n.level, "page": n.page, "children": tree(n.children)}
                for n in nodes
            ]

        assert result.topic_tree is not None and tree(result.topic_tree) == expected
        markdown = (await object_storage.get_object(bucket="documents", key=parsed_key)).decode()
        refs = set(re.findall(r'::image\{id="(img_\d+)"\}', markdown))
        assert refs and {item.object_key for item in images} == {f"{document.id}/{ref}.png" for ref in refs}
        assert all(item.page is not None and item.width and item.height and item.topic_id for item in images)
        for item in images:
            assert await object_storage.get_object(bucket="images", key=item.object_key)

        await object_storage.put_object(bucket="images", key=orphan, data=b"orphan", content_type="image/png")
        async with session_factory() as session, session.begin():
            await DocumentRepository(session).set_status(document.id, DocumentStatus.FAILED)
        await service.parse(document.id)
        async with session_factory() as session:
            repeated = await ImageRepository(session).list_by_document(document.id)
        assert {item.object_key for item in repeated} == {item.object_key for item in images}
        assert len(repeated) == len(images)
        with pytest.raises(ObjectNotFoundError):
            await object_storage.get_object(bucket="images", key=orphan)
    finally:
        await object_storage.delete_prefix(bucket="images", prefix=f"{document.id}/")
        await object_storage.delete_object(bucket="documents", key=key)
        await object_storage.delete_object(bucket="documents", key=parsed_key)
