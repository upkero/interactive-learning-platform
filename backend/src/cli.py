"""Management CLI of the Grasp backend.

Commands:
- ``seed-dev``  — fill the database with demo users/documents/widgets;
- ``seed-primitives`` — sync the primitives catalog from @grasp/primitives;
- ``reembed-descriptions`` — recompute widget-description vectors (2.3).

Usage: ``python -m src.cli <command> <flags>``
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

import anyio.to_thread

from src.app.core.settings.app import get_app_settings
from src.app.core.settings.embeddings import get_embeddings_settings
from src.app.core.settings.seed import get_seed_settings
from src.app.db.session import build_engine, build_session_factory
from src.app.embeddings.factory import get_embedder
from src.app.exceptions.embeddings import EmbeddingResultMismatchError
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
from src.app.seed.dev_seed import seed_dev
from src.app.seed.primitives_seed import load_catalog, resolve_catalog_path, seed_primitives


async def _run_seed_dev(fake_embeddings: bool) -> int:
    """Open a dedicated engine for the CLI process and seed demo data."""
    settings = get_app_settings()
    engine = build_engine(str(settings.db_url), null_pool=True)
    try:
        session_factory = build_session_factory(engine)
        password = get_seed_settings().seed_password
        outcome = await seed_dev(session_factory, password=password, fake_embeddings=fake_embeddings)
        print(f"seed-dev: {outcome}")
    finally:
        await engine.dispose()
    return 0


async def _run_reembed_descriptions() -> int:
    """Recompute every widget description with the configured model.

    Switching EMBEDDINGS_PROVIDER changes the vectors, not the schema: the
    column is vector(1024) for both models. Pages are fetched and committed
    in keyset batches, and the CPU-bound encode runs outside the session so
    a long batch does not hold a database connection.
    """
    embeddings_settings = get_embeddings_settings()
    embedder = get_embedder(embeddings_settings)
    app_settings = get_app_settings()
    engine = build_engine(str(app_settings.db_url), null_pool=True)
    updated = 0
    after: UUID | None = None
    try:
        session_factory = build_session_factory(engine)
        while True:
            async with session_factory() as session:
                batch = await WidgetDescriptionRepository(session).list_batch(
                    after_id=after,
                    limit=embeddings_settings.batch_size,
                )
            if not batch:
                break
            vectors = await anyio.to_thread.run_sync(embedder.embed, [row.text for row in batch])
            if len(vectors) != len(batch):
                raise EmbeddingResultMismatchError("Embedder returned a different number of vectors.")
            if any(len(vector) != embedder.dimension for vector in vectors):
                raise EmbeddingResultMismatchError("Embedder returned a vector of the wrong dimension.")
            async with session_factory() as session, session.begin():
                repository = WidgetDescriptionRepository(session)
                for row, vector in zip(batch, vectors, strict=True):
                    await repository.set_embedding(row.id, vector)
            updated += len(batch)
            after = batch[-1].id
        print(f"reembed-descriptions: updated {updated} rows with {embedder.model_name}")
    finally:
        await engine.dispose()
    return 0


async def _run_seed_primitives(catalog: Path | None) -> int:
    """Validate the catalog, then open a dedicated engine and sync it.

    A missing, unreadable or invalid catalog is a user error: it is reported as one line
    on stderr with exit code 1, before any database connection. Settings and
    database errors are not caught and keep their traceback.
    """
    try:
        catalog_path = resolve_catalog_path(catalog)
        catalog_file = await load_catalog(catalog_path)
    except (OSError, ValueError) as exc:
        print(f"seed-primitives: {exc}", file=sys.stderr)
        return 1
    settings = get_app_settings()
    engine = build_engine(str(settings.db_url), null_pool=True)
    try:
        session_factory = build_session_factory(engine)
        async with session_factory() as session, session.begin():
            count = await seed_primitives(session, catalog_file)
        print(f"seed-primitives: upserted {count} primitives from {catalog_path}")
    finally:
        await engine.dispose()
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Argument parser of the management CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Grasp backend management commands (seeding).",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    seed_dev_parser = subcommands.add_parser(
        "seed-dev",
        help="Seed demo users, documents, parts and widgets (idempotent).",
    )
    seed_dev_parser.add_argument(
        "--fake-embeddings",
        action="store_true",
        help="Generate deterministic hash-based embeddings for widget descriptions.",
    )

    catalog_parser = subcommands.add_parser(
        "seed-primitives",
        help="Sync the primitives catalog published by @grasp/primitives.",
    )
    catalog_parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Path to catalog.json (default: backend resources).",
    )
    subcommands.add_parser(
        "reembed-descriptions",
        help="Recompute widget-description embeddings with the configured model.",
    )
    subcommands.add_parser("export-openapi", help="Export the API schema to backend/openapi.json.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint used by ``python -m src.cli``."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "seed-dev":
        return asyncio.run(_run_seed_dev(fake_embeddings=args.fake_embeddings))
    if args.command == "seed-primitives":
        return asyncio.run(_run_seed_primitives(catalog=args.catalog))
    if args.command == "reembed-descriptions":
        return asyncio.run(_run_reembed_descriptions())
    if args.command == "export-openapi":
        from src.main import app

        destination = Path(__file__).resolve().parents[1] / "openapi.json"
        destination.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"export-openapi: {destination}")
        return 0
    parser.error(f"Unknown command: {args.command}")  # pragma: no cover
    return 2


if __name__ == "__main__":
    sys.exit(main())
