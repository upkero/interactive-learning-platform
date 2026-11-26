"""Idempotent seeding of demo users, documents and widgets for development.

Produces the data needed to open the demo screens without running the
generation pipeline (story 1.2.8):

- Alice and Bob (password from ``SEED_PASSWORD``);
- a document in the ``parsed`` status with a topic tree and no queued parts;
- a document in the ``done`` status with one published part whose
  content comes from a fixture;
- 5-10 config widgets with text descriptions.

JSON fixtures live in ``tests/support/fixtures/seed``; the ``seed``
compose profile mounts them into the runtime image.
"""

import asyncio
import json
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import DocumentStatus, MaterialRole, PartStatus, SourceType
from src.app.contracts.users.user_record import UserRecord
from src.app.contracts.widgets import UsageStatus, WidgetKind, WidgetUsageDraft
from src.app.core.fixtures import PUBLISHED_PART_FIXTURE
from src.app.core.settings.quota import get_quota_settings
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
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
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.storage.object_keys import image_key, parsed_markdown_key, source_key

ALICE_EMAIL: Final[str] = "alice@example.com"
BOB_EMAIL: Final[str] = "bob@example.com"

# backend/src/app/seed -> backend; fixtures live under backend/tests/support.
# In the runtime image the seed compose profile mounts them at the same path.
FIXTURES_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "tests" / "support" / "fixtures" / "seed"

TOPIC_TREE: Final[list[dict[str, Any]]] = [
    {
        "id": "topic-adaptive",
        "title": "Adaptive learning",
        "level": 1,
        "start": 0,
        "end": 1200,
        "own_tokens": 142,
        "total_tokens": 320,
        "page": 1,
        "image_ids": [],
        "children": [
            {
                "id": "topic-chunking",
                "title": "Semantic chunking",
                "level": 2,
                "start": 0,
                "end": 600,
                "own_tokens": 178,
                "total_tokens": 178,
                "page": 1,
                "image_ids": [],
                "children": [],
            },
            {
                "id": "topic-tree",
                "title": "Topic tree",
                "level": 2,
                "start": 600,
                "end": 1200,
                "own_tokens": 0,
                "total_tokens": 0,
                "page": 1,
                "image_ids": [],
                "children": [],
            },
        ],
    },
    {
        "id": "topic-quota",
        "title": "Quota and generation pipeline",
        "level": 1,
        "start": 1200,
        "end": 1800,
        "own_tokens": 96,
        "total_tokens": 96,
        "page": 2,
        "image_ids": [],
        "children": [],
    },
]

# Screen E6: the done document needs its own tree for topic navigation.
DONE_TOPIC_TREE: Final[list[dict[str, Any]]] = [
    {
        "id": "topic-neurons",
        "title": "From neurons to layers",
        "level": 1,
        "start": 0,
        "end": 900,
        "own_tokens": 200,
        "total_tokens": 200,
        "page": 1,
        "image_ids": [],
        "children": [],
    },
    {
        "id": "topic-training",
        "title": "Training and activation",
        "level": 1,
        "start": 900,
        "end": 1600,
        "own_tokens": 150,
        "total_tokens": 150,
        "page": 2,
        "image_ids": [],
        "children": [],
    },
]


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
    monthly_limit = get_quota_settings().default_monthly_limit
    alice = await user_repository.create(
        email=ALICE_EMAIL,
        password_hash=password_hash,
        display_name="Alice",
        monthly_limit=monthly_limit,
    )
    bob = await user_repository.create(
        email=BOB_EMAIL,
        password_hash=password_hash,
        display_name="Bob",
        monthly_limit=monthly_limit,
    )
    return alice, bob


async def _seed_documents(
    session: AsyncSession, alice: UserRecord, bob: UserRecord, ledger: QuotaLedger, storage: ObjectStorageClient
) -> tuple[DocumentRecord, list[PartRecord]]:
    """Create the parsed and the done document, both with a topic tree."""
    document_repository = DocumentRepository(session)
    material_repository = UserMaterialRepository(session)
    part_repository = DocumentPartRepository(session)

    # Screen E1: a document parsed into parts, ready for generation.
    overview_id = uuid4()
    introduction = await asyncio.to_thread((FIXTURES_DIR / "introduction.md").read_bytes)
    doc_overview = await document_repository.create(
        id=overview_id,
        owner_id=alice.id,
        title="Introduction to adaptive learning",
        source_type=SourceType.UPLOAD,
        object_key=source_key(alice.id, overview_id, "md"),
        mime_type="text/markdown",
        size_bytes=len(introduction),
        checksum=sha256(introduction).hexdigest(),
    )
    parsed = await document_repository.set_status(doc_overview.id, DocumentStatus.PARSED)
    if parsed is None:  # pragma: no cover - impossible on a fresh row
        raise RuntimeError("Fresh document not found after create")
    await document_repository.set_topic_tree(parsed.id, TOPIC_TREE)

    # Screen E6: a fully generated document with one published part.
    networks_id = uuid4()
    networks_source = await asyncio.to_thread((FIXTURES_DIR / "neural-networks.md").read_bytes)
    doc_networks = await document_repository.create(
        id=networks_id,
        owner_id=bob.id,
        title="Neural networks basics",
        source_type=SourceType.GDOCS,
        object_key=source_key(bob.id, networks_id, "md"),
        mime_type="text/markdown",
        size_bytes=len(networks_source),
        checksum=sha256(networks_source).hexdigest(),
        source_uri="https://docs.google.com/document/d/demo",
    )
    done = await document_repository.set_status(doc_networks.id, DocumentStatus.DONE)
    if done is None:  # pragma: no cover - impossible on a fresh row
        raise RuntimeError("Fresh document not found after create")
    await document_repository.set_topic_tree(done.id, DONE_TOPIC_TREE)

    published = json.loads(await asyncio.to_thread(PUBLISHED_PART_FIXTURE.read_text, encoding="utf-8"))
    published_quota = await ledger.reserve(session, user_id=bob.id, document_id=done.id, parts=1)
    (part,) = await part_repository.add_many(
        done.id,
        [
            PartDraft(
                index=int(published["index"]),
                title=str(published["title"]),
                topic_ids=list(published.get("topic_ids", [])),
                source_markdown=str(published["source_markdown"]),
                token_count=int(published["token_count"]),
                quota_period_start=published_quota.period.start,
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
    await ledger.charge(session, part_id=part.id)

    await material_repository.create(user_id=alice.id, document_id=parsed.id, role=MaterialRole.OWNER)
    await material_repository.create(user_id=bob.id, document_id=done.id, role=MaterialRole.OWNER)
    await material_repository.create(
        user_id=bob.id, document_id=parsed.id, role=MaterialRole.SHARED, shared_by=alice.id
    )

    image_repository = ImageRepository(session)
    await image_repository.add_many(
        done.id,
        [ImageDraft(object_key=image_key(done.id, 1), width=640, height=480)],
    )
    # Network operations precede commit: failure leaves no committed demo rows.
    for document, data in ((parsed, introduction), (done, networks_source)):
        await storage.put_object(bucket="documents", key=document.object_key, data=data, content_type="text/markdown")
        await storage.put_object(
            bucket="documents",
            key=parsed_markdown_key(document.owner_id, document.id),
            data=data,
            content_type="text/markdown",
        )
    image = await asyncio.to_thread((FIXTURES_DIR / "figure-neuron.png").read_bytes)
    await storage.put_object(bucket="images", key=image_key(done.id, 1), data=image, content_type="image/png")
    return parsed, [part]


async def _seed_widgets(
    session: AsyncSession,
    published_parts: Sequence[PartRecord],
    *,
    fake_embeddings: bool,
) -> int:
    """Create config widgets on Bob's published document."""
    widget_specs: list[dict[str, Any]] = await _load_fixture("widgets.json")
    widget_repository = WidgetRepository(session)
    description_repository = WidgetDescriptionRepository(session)
    usage_repository = WidgetUsageRepository(session)

    for index, spec in enumerate(widget_specs):
        part = published_parts[index % len(published_parts)]
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
    ledger: QuotaLedger,
    storage: ObjectStorageClient,
    fake_embeddings: bool = False,
) -> str:
    """Fill the database with demo data; safe to run repeatedly.

    Returns ``"already seeded"`` when the demo users exist, otherwise
    ``"seeded ..."`` with the counts after the inserts complete.
    """
    hasher = PasswordHash.recommended()
    password_hash = await asyncio.to_thread(hasher.hash, password)

    async with session_factory() as session, session.begin():
        user_repository = UserRepository(session)
        if await user_repository.get_by_email(ALICE_EMAIL) is not None:
            return "already seeded"

        primitives_count = await _seed_primitives(session)
        alice, bob = await _seed_users(session, password_hash)
        doc_parsed, published_parts = await _seed_documents(session, alice, bob, ledger, storage)
        widgets_count = await _seed_widgets(session, published_parts, fake_embeddings=fake_embeddings)

    summary = (
        f"seeded: {primitives_count} primitives, 2 users, 2 documents, "
        f"0 queued parts (parsed doc {doc_parsed.id}), {len(published_parts)} published part, {widgets_count} widgets"
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
