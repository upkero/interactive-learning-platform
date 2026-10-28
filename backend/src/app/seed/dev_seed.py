"""Idempotent seeding of demo users, documents and widgets for development.

Produces the data needed to open the demo screens without running the
generation pipeline (story 1.2.8):

- Alice and Bob (password from ``SEED_PASSWORD``);
- a document in the ``parsed`` status with a topic tree;
- a document in the ``done`` status with one published part whose
  content comes from a fixture;
- 5-10 config widgets with text descriptions.

JSON fixtures live in ``tests/support/fixtures/seed``; the ``seed``
compose profile mounts them into the runtime image.
"""

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import DocumentStatus, MaterialRole, PartStatus, SourceType
from src.app.contracts.users.user_record import UserRecord
from src.app.contracts.widgets import UsageStatus, WidgetKind, WidgetUsageDraft
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
from src.app.seed.embeddings import fake_embedding
from src.app.seed.primitives_seed import seed_primitives_from_catalog

ALICE_EMAIL: Final[str] = "alice@grasp.local"
BOB_EMAIL: Final[str] = "bob@grasp.local"

# backend/src/app/seed -> backend; fixtures live under backend/tests/support.
# In the runtime image the seed compose profile mounts them at the same path.
FIXTURES_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "tests" / "support" / "fixtures" / "seed"

TOPIC_TREE: Final[dict[str, Any]] = {
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

# Screen E6: the done document needs its own tree for topic navigation.
DONE_TOPIC_TREE: Final[dict[str, Any]] = {
    "topics": [
        {
            "id": "topic-neurons",
            "title": "From neurons to layers",
            "children": [],
        },
        {"id": "topic-training", "title": "Training and activation", "children": []},
    ]
}


async def _load_fixture(name: str) -> Any:
    """Read a JSON fixture off the event loop thread."""
    payload = await asyncio.to_thread((FIXTURES_DIR / name).read_text, encoding="utf-8")
    return json.loads(payload)


async def _seed_primitives(session: AsyncSession) -> int:
    """Upsert the demo primitives catalog shipped in the seed fixtures."""
    return await seed_primitives_from_catalog(session, FIXTURES_DIR / "primitives.json")


async def _seed_users(session: AsyncSession, password_hash: str) -> tuple[UserRecord, UserRecord]:
    """Create the two demo users; the caller owns the idempotency check."""
    user_repository = UserRepository(session)
    alice = await user_repository.create(
        email=ALICE_EMAIL,
        password_hash=password_hash,
        display_name="Alice",
    )
    bob = await user_repository.create(
        email=BOB_EMAIL,
        password_hash=password_hash,
        display_name="Bob",
    )
    return alice, bob


async def _seed_documents(
    session: AsyncSession, alice: UserRecord, bob: UserRecord
) -> tuple[DocumentRecord, list[PartRecord]]:
    """Create the parsed and the done document, both with a topic tree."""
    document_repository = DocumentRepository(session)
    material_repository = UserMaterialRepository(session)
    part_repository = DocumentPartRepository(session)

    # Screen E1: a document parsed into parts, ready for generation.
    doc_overview = await document_repository.create(
        owner_id=alice.id,
        title="Introduction to adaptive learning",
        source_type=SourceType.UPLOAD,
        object_key="docs/demo/introduction.md",
        mime_type="text/markdown",
        size_bytes=4096,
        checksum="d" * 64,
    )
    parsed = await document_repository.set_status(doc_overview.id, DocumentStatus.PARSED)
    if parsed is None:  # pragma: no cover - impossible on a fresh row
        raise RuntimeError("Fresh document not found after create")
    await document_repository.set_topic_tree(parsed.id, TOPIC_TREE)
    overview_parts = await part_repository.add_many(
        parsed.id,
        [
            PartDraft(
                index=0,
                title="What adaptive learning is",
                topic_ids=["topic-adaptive", "topic-chunking"],
                source_markdown="# What adaptive learning is\nContent of part one.",
                token_count=142,
                profile={"difficulty": "beginner"},
            ),
            PartDraft(
                index=1,
                title="Topic tree and semantic chunks",
                topic_ids=["topic-chunking", "topic-tree"],
                source_markdown="# Topic tree and semantic chunks\nContent of part two.",
                token_count=178,
                profile={"difficulty": "beginner"},
            ),
            PartDraft(
                index=2,
                title="Quota and generation pipeline",
                topic_ids=["topic-quota"],
                source_markdown="# Quota and generation pipeline\nContent of part three.",
                token_count=96,
                profile={"difficulty": "intermediate"},
            ),
        ],
    )

    # Screen E6: a fully generated document with one published part.
    doc_networks = await document_repository.create(
        owner_id=bob.id,
        title="Neural networks basics",
        source_type=SourceType.GDOCS,
        object_key="docs/demo/neural-networks",
        mime_type="text/html",
        size_bytes=1024 * 1024,
        checksum="f" * 64,
        source_uri="https://docs.google.com/document/d/demo",
    )
    done = await document_repository.set_status(doc_networks.id, DocumentStatus.DONE)
    if done is None:  # pragma: no cover - impossible on a fresh row
        raise RuntimeError("Fresh document not found after create")
    await document_repository.set_topic_tree(done.id, DONE_TOPIC_TREE)

    published = await _load_fixture("published_part.json")
    (part,) = await part_repository.add_many(
        done.id,
        [
            PartDraft(
                index=int(published["index"]),
                title=str(published["title"]),
                topic_ids=list(published.get("topic_ids", [])),
                source_markdown=str(published["source_markdown"]),
                token_count=int(published["token_count"]),
                profile=dict(published["profile"]),
                content=dict(published["content"]),
            )
        ],
    )
    transitioned = await part_repository.transition(
        part.id,
        expected=frozenset({PartStatus.QUEUED}),
        to=PartStatus.PUBLISHED,
    )
    if not transitioned:  # pragma: no cover - impossible on a fresh base
        raise RuntimeError("Seeded part failed to publish from the queued state")

    await material_repository.create(user_id=alice.id, document_id=parsed.id, role=MaterialRole.OWNER)
    await material_repository.create(user_id=bob.id, document_id=done.id, role=MaterialRole.OWNER)
    await material_repository.create(
        user_id=bob.id, document_id=parsed.id, role=MaterialRole.SHARED, shared_by=alice.id
    )

    image_repository = ImageRepository(session)
    await image_repository.add_many(
        done.id,
        [ImageDraft(object_key="images/demo/figure-neuron.png", width=640, height=480)],
    )
    return parsed, overview_parts


async def _seed_widgets(
    session: AsyncSession,
    overview_parts: Sequence[PartRecord],
    *,
    fake_embeddings: bool,
) -> int:
    """Create config widgets with descriptions and usages on the parsed document."""
    widget_specs: list[dict[str, Any]] = await _load_fixture("widgets.json")
    widget_repository = WidgetRepository(session)
    description_repository = WidgetDescriptionRepository(session)
    usage_repository = WidgetUsageRepository(session)

    for index, spec in enumerate(widget_specs):
        part = overview_parts[index % len(overview_parts)]
        widget = await widget_repository.create(
            kind=WidgetKind(spec["kind"]),
            primitive_id=spec.get("primitive_id"),
            mode=spec.get("mode"),
            params=spec.get("params"),
            source_tsx=spec.get("source_tsx"),
            compiled_js=spec.get("compiled_js"),
            created_from_part_id=part.id,
        )
        if fake_embeddings:
            for description in spec["descriptions"]:
                await description_repository.create(
                    widget_id=widget.id,
                    text=description["text"],
                    is_paraphrase=bool(description["is_paraphrase"]),
                    embedding=fake_embedding(description["text"]),
                )
        await usage_repository.add_many(
            part.id,
            [
                WidgetUsageDraft(
                    directive_ref=spec["directive_ref"],
                    position=int(spec["position"]),
                    widget_id=widget.id,
                    status=UsageStatus.READY if fake_embeddings else UsageStatus.PENDING,
                )
            ],
        )
    return len(widget_specs)


async def seed_dev(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    password: str,
    fake_embeddings: bool = False,
) -> str:
    """Fill the database with demo data; safe to run repeatedly.

    Returns ``"already seeded"`` when the demo users exist, otherwise
    ``"seeded ..."`` with the counts after the inserts complete.
    """
    hasher = PasswordHash.recommended()
    password_hash = hasher.hash(password)

    async with session_factory() as session, session.begin():
        user_repository = UserRepository(session)
        if await user_repository.get_by_email(ALICE_EMAIL) is not None:
            return "already seeded"

        primitives_count = await _seed_primitives(session)
        alice, bob = await _seed_users(session, password_hash)
        doc_parsed, overview_parts = await _seed_documents(session, alice, bob)
        widgets_count = await _seed_widgets(session, overview_parts, fake_embeddings=fake_embeddings)

    summary = (
        f"seeded: {primitives_count} primitives, 2 users, 2 documents, "
        f"{len(overview_parts)} queued parts (doc {doc_parsed.id}), {widgets_count} widgets"
    )
    if not fake_embeddings:
        summary += " (widget descriptions skipped without --fake-embeddings)"
    return summary


__all__ = [
    "ALICE_EMAIL",
    "BOB_EMAIL",
    "FIXTURES_DIR",
    "seed_dev",
]
