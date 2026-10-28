"""Integration test 1.2.8: ``seed-dev`` is idempotent and shapes demo data.

Runs the full ``seed_dev`` twice against real Postgres: the first run
inserts the demo dataset, the second one must be a no-op returning
``"already seeded"`` without duplicating rows.
"""

import pytest
from sqlalchemy import func, select

from src.app.contracts.documents.statuses import DocumentStatus, PartStatus, SourceType
from src.app.models.document import Document
from src.app.models.document_part import DocumentPart
from src.app.models.user import User
from src.app.models.widget import Widget
from src.app.seed.dev_seed import ALICE_EMAIL, BOB_EMAIL, seed_dev
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


async def test_seed_dev_is_idempotent(session_factory: SessionFactory) -> None:
    """Second seed run is a no-op; the demo dataset stays intact."""
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(User))) == 0

    first = await seed_dev(session_factory, password="seed-test-password", fake_embeddings=True)
    second = await seed_dev(session_factory, password="seed-test-password", fake_embeddings=True)

    assert first.startswith("seeded")
    assert second == "already seeded"

    async with session_factory() as session:
        user_count = await session.scalar(select(func.count()).select_from(User))
        assert user_count == 2
        widget_count = await session.scalar(select(func.count()).select_from(Widget))
        assert widget_count is not None and widget_count > 0

        documents = (await session.scalars(select(Document).order_by(Document.title))).all()
        assert len(documents) == 2
        by_status = {doc.status: doc for doc in documents}
        assert set(by_status) == {DocumentStatus.PARSED.value, DocumentStatus.DONE.value}

        # Screen E1: parsed document carries a topic tree.
        parsed = by_status[DocumentStatus.PARSED.value]
        owner = await session.scalar(select(User.email).where(User.id == parsed.owner_id))
        assert owner == ALICE_EMAIL
        assert parsed.topic_tree is not None and "topics" in parsed.topic_tree
        assert parsed.source_type == SourceType.UPLOAD.value
        # Screen E6: done document holds exactly one published part with content.
        done = by_status[DocumentStatus.DONE.value]
        done_owner = await session.scalar(select(User.email).where(User.id == done.owner_id))
        assert done_owner == BOB_EMAIL
        assert done.source_type == SourceType.GDOCS.value and done.source_uri is not None
        assert done.topic_tree is not None and "topics" in done.topic_tree
        part = (
            await session.scalars(
                select(DocumentPart).where(
                    DocumentPart.document_id == done.id, DocumentPart.status == PartStatus.PUBLISHED.value
                )
            )
        ).one()
        assert part.content is not None and "markdown" in part.content
        assert part.published_at is not None
