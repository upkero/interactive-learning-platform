"""Unit tests 1.4.5: the topic tree read with token sums."""

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.app.contracts.documents import (
    DocumentStatus,
    MaterialRole,
    PartDraft,
    PartStatus,
    SourceType,
)
from src.app.exceptions.documents import DocumentNotFoundError, DocumentNotReadyError
from src.app.services.documents.document_query_service import DocumentQueryService
from tests.support.fakes.repositories.documents import (
    FakeDocumentPartRepository,
    FakeDocumentRepository,
    FakeUserMaterialRepository,
)
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient

pytestmark = pytest.mark.unit

# same shape as the seed's TOPIC_TREE
_TREE: dict[str, Any] = {
    "topics": [
        {
            "id": "topic-adaptive",
            "title": "Adaptive learning",
            "children": [
                {"id": "topic-chunking", "title": "Semantic chunking", "children": []},
                {"id": "topic-tree", "title": "Topic tree", "children": []},
            ],
        },
        {"id": "topic-quota", "title": "Quota and generation pipeline", "children": []},
    ]
}


def _service() -> tuple[
    DocumentQueryService,
    FakeDocumentRepository,
    FakeUserMaterialRepository,
    FakeDocumentPartRepository,
]:
    documents = FakeDocumentRepository()
    materials = FakeUserMaterialRepository()
    parts = FakeDocumentPartRepository()
    service = DocumentQueryService(
        documents=documents,
        materials=materials,
        parts=parts,
        storage=FakeObjectStorageClient(),
    )
    return service, documents, materials, parts


async def _document_with_access(
    documents: FakeDocumentRepository,
    materials: FakeUserMaterialRepository,
    *,
    status: DocumentStatus = DocumentStatus.PARSED,
    topic_tree: dict[str, Any] | None = _TREE,
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


async def test_tree_matches_seed_shape_with_subtree_token_sums() -> None:
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
                profile={},
            ),
            PartDraft(
                index=1,
                title="Topic tree and semantic chunks",
                topic_ids=["topic-chunking", "topic-tree"],
                source_markdown="part two",
                token_count=178,
                profile={},
            ),
            PartDraft(
                index=2,
                title="Quota and generation pipeline",
                topic_ids=["topic-quota"],
                source_markdown="part three",
                token_count=96,
                profile={},
            ),
        ],
    )

    tree: dict[str, Any] = await service.get_topic_tree(user_id=owner, document_id=document_id)
    topics = tree["topics"]
    assert [t["id"] for t in topics] == ["topic-adaptive", "topic-quota"]

    adaptive, quota = topics[0], topics[1]
    # quota: only its own part
    assert quota["tokens"] == 96
    assert quota["level"] == 1
    assert quota["children"] == []
    # adaptive: parts 0 and 1 touch its subtree (no double counting of
    # part 1 despite being assigned to both chunking and tree)
    assert adaptive["tokens"] == 320
    chunking, tree_node = adaptive["children"]
    assert (chunking["id"], chunking["tokens"], chunking["level"]) == ("topic-chunking", 320, 2)
    assert (tree_node["id"], tree_node["tokens"], tree_node["level"]) == ("topic-tree", 178, 2)


async def test_shared_user_reads_the_tree_too() -> None:
    service, documents, materials, _parts = _service()
    _owner, document_id = await _document_with_access(documents, materials)
    stranger = uuid4()
    await materials.create(user_id=stranger, document_id=document_id, role=MaterialRole.SHARED)

    tree: dict[str, Any] = await service.get_topic_tree(user_id=stranger, document_id=document_id)
    assert tree["topics"][0]["id"] == "topic-adaptive"


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
    await documents.set_status(document_id, DocumentStatus.FAILED, error="parse_failed")

    with pytest.raises(DocumentNotReadyError) as exc_info:
        await service.get_topic_tree(user_id=owner, document_id=document_id)
    assert exc_info.value.detail == "parse_failed"


async def test_no_access_is_404() -> None:
    service, documents, materials, _parts = _service()
    _owner, document_id = await _document_with_access(documents, materials)
    with pytest.raises(DocumentNotFoundError):
        await service.get_topic_tree(user_id=uuid4(), document_id=document_id)


async def test_failed_parts_do_not_contribute_tokens() -> None:
    service, documents, materials, parts = _service()
    owner, document_id = await _document_with_access(documents, materials)
    created = await parts.add_many(
        document_id,
        [
            PartDraft(
                index=0,
                title="ok",
                topic_ids=["topic-quota"],
                source_markdown="ok",
                token_count=100,
                profile={},
            ),
            PartDraft(
                index=1,
                title="broken",
                topic_ids=["topic-quota"],
                source_markdown="broken",
                token_count=50,
                profile={},
            ),
        ],
    )
    failed = await parts.transition(created[1].id, frozenset({PartStatus.QUEUED}), PartStatus.FAILED)
    assert failed

    tree: dict[str, Any] = await service.get_topic_tree(user_id=owner, document_id=document_id)
    assert tree["topics"][1]["tokens"] == 100
