"""Check preview against parts generated through the API and saved to Postgres."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.api.v1.middleware.rate_limit import limiter
from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents import DocumentStatus, MaterialRole, SourceType
from src.app.contracts.quota import LedgerOp
from src.app.ingest.tokens import get_token_counter
from src.app.ingest.topic_tree import build_topic_tree
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.storage.object_keys import parsed_markdown_key
from src.main import create_app
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("selected", "minimum_parts"),
    [(["1", "2", "3"], 3), (["1.1", "3.1"], 2), (["2", "2.2"], 2), (["0"], 1)],
    ids=["all-chapters", "scattered-selection", "parent-and-child", "fence-and-whitespace-tail"],
)
async def test_preview_matches_persisted_generation_parts(
    session_factory: async_sessionmaker[AsyncSession], selected: list[str], minimum_parts: int
) -> None:
    paragraph = "The lesson explains how a concept changes when its input changes. " * 18 + "\n\n"
    markdown = (
        "# First chapter\n\n## First section\n\n"
        + paragraph * 55
        + "# Long chapter\n\n## First section\n\n"
        + paragraph * 55
        + "## Second section\n\n"
        + paragraph * 55
        + "## Third section\n\n"
        + paragraph * 55
        + "# Last chapter\n\n## Last section\n\n"
        + paragraph * 55
    )
    if selected == ["0"]:
        markdown = "```python\n" + "word " * 15_547 + "\n```\n" + "  \n" * 5
    counter = get_token_counter()
    tree = build_topic_tree(markdown, counter)
    app = create_app()
    limiter.reset()
    with TestClient(app, raise_server_exceptions=False) as client:
        container: ApplicationContainer = app.state.container
        container.__dict__["task_dispatcher"] = FakeTaskDispatcher()
        if selected != ["0"]:
            assert tree[1].total_tokens > container.ingest_settings.split_max_tokens
        email = f"splitting-{uuid4()}@example.com"
        registered = client.post("/api/v1/auth/register", json={"email": email, "password": "long-enough-password"})
        assert registered.status_code == 201, registered.text
        data = markdown.encode()
        async with session_factory() as session, session.begin():
            user = await UserRepository(session).get_by_email(email)
            assert user is not None
            documents = DocumentRepository(session)
            document = await documents.create(
                owner_id=user.id,
                title="Course",
                source_type=SourceType.UPLOAD,
                object_key="course.md",
                mime_type="text/markdown",
                size_bytes=len(data),
                checksum="d" * 64,
            )
            await UserMaterialRepository(session).create(
                user_id=user.id, document_id=document.id, role=MaterialRole.OWNER
            )
            await documents.set_topic_tree(document.id, [node.to_dict() for node in tree])
            await documents.set_status(document.id, DocumentStatus.PARSED)
        await container.object_storage.put_object(
            bucket="documents", key=parsed_markdown_key(user.id, document.id), data=data, content_type="text/markdown"
        )
        path = f"/api/v1/documents/{document.id}"
        preview = client.post(f"{path}/plan", json={"topic_ids": selected})
        assert preview.status_code == 200, preview.text
        generated = client.post(
            f"{path}/generate",
            json={"topic_ids": selected, "answers": {"level": "novice", "goal": "exam", "depth": "standard"}},
        )
        assert generated.status_code == 202, generated.text
        plan = preview.json()
        started = generated.json()
        ids = tuple(UUID(value) for value in started["part_ids"])
        assert plan["cost"] == started["cost"] == len(ids) == len(plan["parts"])
        assert len(ids) >= minimum_parts

        async with session_factory() as session:
            parts = (
                await session.scalars(
                    select(DocumentPart).where(DocumentPart.document_id == document.id).order_by(DocumentPart.index)
                )
            ).all()
            reserve = (
                await session.scalars(select(GenerationLedger).where(GenerationLedger.document_id == document.id))
            ).one()
        assert tuple(part.id for part in parts) == ids
        assert [(part.index, part.title, part.token_count) for part in parts] == [
            (part["index"], part["title"], part["tokens"]) for part in plan["parts"]
        ]
        assert (reserve.op, reserve.delta) == (LedgerOp.RESERVE.value, -len(parts))
        assert all(part.quota_period_start == reserve.period_start for part in parts)
        assert all(
            part.source_markdown.strip() and counter.count(part.source_markdown) == part.token_count for part in parts
        )
        if selected == ["0"]:
            assert len(parts) == 1
            assert parts[0].source_markdown == markdown.rstrip(" \n") + "\n"
