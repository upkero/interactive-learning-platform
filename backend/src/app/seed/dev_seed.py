"""Idempotent seeding of demo users, documents and widgets for development."""

import asyncio
import json
from pathlib import Path
from typing import Any

from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import MaterialRole, SourceType
from src.app.contracts.widgets import WidgetKind
from src.app.repositories.document_part_repository import (
    DocumentPartRepository,
)
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.primitive_repository import PrimitiveRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_description_repository import (
    WidgetDescriptionRepository,
)
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
from src.app.seed.embeddings import fake_embedding

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ALICE_EMAIL = "alice@grasp.local"
BOB_EMAIL = "bob@grasp.local"


async def _seed_primitives_bundle(session: AsyncSession) -> int:
    """Upsert the primitives shipped with the repository (demo catalog)."""
    payload = await asyncio.to_thread((FIXTURES_DIR / "primitives.json").read_text, encoding="utf-8")
    items: list[dict[str, Any]] = json.loads(payload)
    repository = PrimitiveRepository(session)
    for item in items:
        await repository.upsert(
            primitive_id=item["id"],
            version=item["version"],
            description=item["description"],
            modes=list(item["modes"]),
            params_schema=dict(item["params_schema"]),
        )
    return len(items)


async def seed_dev(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    password: str,
    fake_embeddings: bool = False,
) -> str:
    """Fill the database with demo data; safe to run repeatedly.

    Returns a human-readable outcome: ``"already seeded"`` when the demo
    users exist, otherwise ``"seeded"`` after the inserts complete.
    """
    hasher = PasswordHash.recommended()
    password_hash = hasher.hash(password)

    async with session_factory() as session, session.begin():
        user_repository = UserRepository(session)
        if await user_repository.get_by_email(ALICE_EMAIL) is not None:
            return "already seeded"

        primitives_count = await _seed_primitives_bundle(session)

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

        document_repository = DocumentRepository(session)
        doc_overview = await document_repository.create(
            owner_id=alice.id,
            title="Introduction to adaptive learning",
            source_type=SourceType.MD,
            object_key="docs/demo/introduction.md",
            mime_type="text/markdown",
            size_bytes=4096,
            checksum="d" * 64,
            source_uri=None,
        )
        doc_networks = await document_repository.create(
            owner_id=bob.id,
            title="Neural networks basics",
            source_type=SourceType.PDF,
            object_key="docs/demo/neural-networks.pdf",
            mime_type="application/pdf",
            size_bytes=1024 * 1024,
            checksum="f" * 64,
            source_uri="https://example.com/neural-networks.pdf",
        )

        material_repository = UserMaterialRepository(session)
        await material_repository.create(
            user_id=alice.id,
            document_id=doc_overview.id,
            role=MaterialRole.OWNER,
        )
        await material_repository.create(
            user_id=bob.id,
            document_id=doc_networks.id,
            role=MaterialRole.OWNER,
        )
        await material_repository.create(
            user_id=bob.id,
            document_id=doc_overview.id,
            role=MaterialRole.SHARED,
            shared_by=alice.id,
        )

        part_repository = DocumentPartRepository(session)
        overview_parts = await part_repository.add_many(
            doc_overview.id,
            [
                {
                    "index": 0,
                    "title": "What adaptive learning is",
                    "topic_ids": ["topic-adaptive", "topic-chunking"],
                    "source_markdown": "# What adaptive learning is\nContent of part one.",
                    "token_count": 142,
                    "profile": {"difficulty": "beginner"},
                },
                {
                    "index": 1,
                    "title": "Topic tree and semantic chunks",
                    "topic_ids": ["topic-chunking", "topic-tree"],
                    "source_markdown": "# Topic tree and semantic chunks\nContent of part two.",
                    "token_count": 178,
                    "profile": {"difficulty": "beginner"},
                },
                {
                    "index": 2,
                    "title": "Quota and generation pipeline",
                    "topic_ids": ["topic-quota"],
                    "source_markdown": "# Quota and generation pipeline\nContent of part three.",
                    "token_count": 96,
                    "profile": {"difficulty": "intermediate"},
                },
            ],
        )
        await part_repository.add_many(
            doc_networks.id,
            [
                {
                    "index": 0,
                    "title": "From neurons to layers",
                    "topic_ids": ["topic-neurons"],
                    "source_markdown": "## From neurons to layers\nContent of part one.",
                    "token_count": 121,
                    "profile": {"difficulty": "beginner"},
                },
                {
                    "index": 1,
                    "title": "Training a model",
                    "topic_ids": ["topic-training"],
                    "source_markdown": "## Training a model\nContent of part two.",
                    "token_count": 154,
                    "profile": {"difficulty": "intermediate"},
                },
            ],
        )

        image_repository = ImageRepository(session)
        await image_repository.add_many(
            doc_networks.id,
            [
                {
                    "object_key": "images/demo/figure-neuron.png",
                    "width": 640,
                    "height": 480,
                }
            ],
        )

        widget_payload = await asyncio.to_thread((FIXTURES_DIR / "widgets.json").read_text, encoding="utf-8")
        widget_specs: list[dict[str, Any]] = json.loads(widget_payload)
        widget_repository = WidgetRepository(session)
        description_repository = WidgetDescriptionRepository(session)
        usage_repository = WidgetUsageRepository(session)
        for index, spec in enumerate(widget_specs):
            part = overview_parts[index % len(overview_parts)]
            widget = await widget_repository.create(
                kind=WidgetKind(spec["kind"]),
                primitive_id=spec["primitive_id"],
                mode=spec["mode"],
                params=spec["params"],
                source_tsx=spec["source_tsx"],
                compiled_js=spec["compiled_js"],
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
                    {
                        "directive_ref": spec["directive_ref"],
                        "widget_id": widget.id,
                        "position": spec["position"],
                        "status": "ready" if fake_embeddings else "pending",
                    }
                ],
            )

    if not fake_embeddings:
        return (
            f"seeded: {primitives_count} primitives, demo users, documents, widgets "
            "(widget descriptions skipped without --fake-embeddings)"
        )
    return f"seeded: {primitives_count} primitives, demo users, documents, widgets, descriptions"


__all__ = [
    "ALICE_EMAIL",
    "BOB_EMAIL",
    "FIXTURES_DIR",
    "seed_dev",
]
