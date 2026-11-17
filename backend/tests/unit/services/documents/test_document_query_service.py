"""Unit tests 1.4.5: the topic tree read with token sums."""

import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import (
    DocumentErrorCode,
    DocumentStatus,
    MaterialRole,
    PartDraft,
    SourceType,
)
from src.app.exceptions.documents import DocumentNotFoundError, DocumentNotReadyError
from src.app.services.documents.document_query_service import DocumentQueryService
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import (
    FakeDocumentPartRepository,
    FakeDocumentRepository,
    FakeUserMaterialRepository,
)
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient

pytestmark = pytest.mark.unit

_TREE_PATH = Path(__file__).resolve().parents[3] / "support" / "fixtures" / "documents" / "tree.json"
_TREE: list[dict[str, Any]] = json.loads(_TREE_PATH.read_text(encoding="utf-8"))


def _service() -> tuple[
    DocumentQueryService,
    FakeDocumentRepository,
    FakeUserMaterialRepository,
    FakeDocumentPartRepository,
]:
    documents = FakeDocumentRepository()
    materials = FakeUserMaterialRepository()
    parts = FakeDocumentPartRepository()
    session = FakeSession()
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    service = DocumentQueryService(
        session_factory=factory,
        documents=lambda _: documents,
        materials=lambda _: materials,
        parts=lambda _: parts,
        storage=FakeObjectStorageClient(),
    )
    return service, documents, materials, parts


async def _document_with_access(
    documents: FakeDocumentRepository,
    materials: FakeUserMaterialRepository,
    *,
    status: DocumentStatus = DocumentStatus.PARSED,
    topic_tree: list[dict[str, Any]] | None = _TREE,
) -> tuple[UUID, UUID]:
    owner = uuid4()
    document = await documents.create(
        owner_id=owner,
        title="Introduction to adaptive learning",
        source_type=SourceType.UPLOAD,
        object_key="docs/demo/introduction.md",
        mime_type="text/markdown",
        size_bytes=4096,
        checksum="d" * 64,
    )
    if status is not DocumentStatus.UPLOADED:
        await documents.set_status(document.id, status)
    if topic_tree is not None and status in (DocumentStatus.PARSED, DocumentStatus.DONE):
        await documents.set_topic_tree(document.id, topic_tree)
    await materials.create(user_id=owner, document_id=document.id, role=MaterialRole.OWNER)
    return owner, document.id


async def test_tree_copies_parser_levels_and_total_tokens() -> None:
    service, documents, materials, parts = _service()
    owner, document_id = await _document_with_access(documents, materials)
    # parts mirror the dev seed: 142 + 178 + 96 tokens
    await parts.add_many(
        document_id,
        [
            PartDraft(
                index=0,
                title="What adaptive learning is",
                topic_ids=["topic-adaptive", "topic-chunking"],
                source_markdown="part one",
                token_count=142,
                quota_period_start=None,
                profile={},
            ),
            PartDraft(
                index=1,
                title="Topic tree and semantic chunks",
                topic_ids=["topic-chunking", "topic-tree"],
                source_markdown="part two",
                token_count=178,
                quota_period_start=None,
                profile={},
            ),
            PartDraft(
                index=2,
                title="Quota and generation pipeline",
                topic_ids=["topic-quota"],
                source_markdown="part three",
                token_count=96,
                quota_period_start=None,
                profile={},
            ),
        ],
    )

    topics = await service.get_topic_tree(user_id=owner, document_id=document_id)
    assert [t.id for t in topics] == ["topic-adaptive", "topic-quota"]

    adaptive, quota = topics[0], topics[1]
    # level and tokens are taken from the parse result, not recalculated
    assert (quota.total_tokens, quota.level, quota.children) == (96, 1, ())
    assert (adaptive.total_tokens, adaptive.level) == (320, 1)
    chunking, tree_node = adaptive.children
    assert (chunking.id, chunking.total_tokens, chunking.level) == ("topic-chunking", 178, 2)
    assert (tree_node.id, tree_node.total_tokens, tree_node.level) == ("topic-tree", 0, 2)


async def test_shared_user_reads_the_tree_too() -> None:
    service, documents, materials, _parts = _service()
    _owner, document_id = await _document_with_access(documents, materials)
    stranger = uuid4()
    await materials.create(user_id=stranger, document_id=document_id, role=MaterialRole.SHARED)

    tree = await service.get_topic_tree(user_id=stranger, document_id=document_id)
    assert tree[0].id == "topic-adaptive"


async def test_uploaded_and_parsing_answer_409_with_status_in_extra() -> None:
    service, documents, materials, _parts = _service()
    for status in (DocumentStatus.UPLOADED, DocumentStatus.PARSING, DocumentStatus.GENERATING):
        owner, document_id = await _document_with_access(documents, materials, status=status)
        with pytest.raises(DocumentNotReadyError) as exc_info:
            await service.get_topic_tree(user_id=owner, document_id=document_id)
        assert exc_info.value.error_code == "document_not_ready"
        assert exc_info.value.extra == {"status": status.value}


async def test_failed_document_answers_409_with_the_parse_error() -> None:
    service, documents, materials, _parts = _service()
    owner, document_id = await _document_with_access(documents, materials, status=DocumentStatus.FAILED)
    await documents.set_status(document_id, DocumentStatus.FAILED, error_code=DocumentErrorCode.PARSE_FAILED)

    with pytest.raises(DocumentNotReadyError) as exc_info:
        await service.get_topic_tree(user_id=owner, document_id=document_id)
    assert exc_info.value.extra == {"status": "failed", "reason": "parse_failed"}


async def test_failed_document_without_reason_does_not_invent_one() -> None:
    service, documents, materials, _parts = _service()
    owner, document_id = await _document_with_access(documents, materials, status=DocumentStatus.FAILED)
    with pytest.raises(DocumentNotReadyError) as exc_info:
        await service.get_topic_tree(user_id=owner, document_id=document_id)
    assert exc_info.value.extra == {"status": "failed", "reason": None}


async def test_no_access_is_404() -> None:
    service, documents, materials, _parts = _service()
    _owner, document_id = await _document_with_access(documents, materials)
    with pytest.raises(DocumentNotFoundError):
        await service.get_topic_tree(user_id=uuid4(), document_id=document_id)


async def test_parts_do_not_change_the_tree_token_sums() -> None:
    # story 1.9 owns the token accounting: adding parts must not shift it
    service, documents, materials, parts = _service()
    owner, document_id = await _document_with_access(documents, materials)
    await parts.add_many(
        document_id,
        [
            PartDraft(
                index=0,
                title="extra",
                topic_ids=["topic-quota"],
                source_markdown="extra",
                token_count=1000,
                quota_period_start=None,
                profile={},
            )
        ],
    )

    tree = await service.get_topic_tree(user_id=owner, document_id=document_id)
    assert tree[1].total_tokens == 96
