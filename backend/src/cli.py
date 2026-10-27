"""Management CLI of the Grasp backend.

Commands:
- ``seed-dev``  — fill the database with demo users/documents/widgets;
- ``seed-primitives`` — sync the primitives catalog from @grasp/primitives.

Usage: ``python -m src.cli <command> <flags>``
"""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from src.app.core.settings.app import get_app_settings
from src.app.db.session import build_engine, build_session_factory
from src.app.seed.dev_seed import seed_dev
from src.app.seed.primitives_seed import resolve_catalog_path, seed_primitives_from_catalog

DEFAULT_SEED_PASSWORD = "grasp123"


async def _run_seed_dev(fake_embeddings: bool) -> int:
    """Open a dedicated engine for the CLI process and seed demo data."""
    settings = get_app_settings()
    engine = build_engine(
        str(settings.db_url),
        pool_size=1,
        max_overflow=0,
        null_pool=True,
    )
    try:
        session_factory = build_session_factory(engine)
        outcome = await seed_dev(
            session_factory,
            password=os.environ.get("SEED_PASSWORD", DEFAULT_SEED_PASSWORD),
            fake_embeddings=fake_embeddings,
        )
        print(f"seed-dev: {outcome}")
    finally:
        await engine.dispose()
    return 0


async def _run_seed_primitives(catalog: Path | None) -> int:
    """Open a dedicated engine for the CLI process and sync the catalog."""
    settings = get_app_settings()
    catalog_path = resolve_catalog_path(catalog)
    engine = build_engine(str(settings.db_url), pool_size=1, max_overflow=0, null_pool=True)
    try:
        session_factory = build_session_factory(engine)
        async with session_factory() as session, session.begin():
            count = await seed_primitives_from_catalog(session, catalog_path)
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
        help="Path to catalog.json (default: published primitives dist).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint used by ``python -m src.cli``."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "seed-dev":
        return asyncio.run(_run_seed_dev(fake_embeddings=args.fake_embeddings))
    if args.command == "seed-primitives":
        return asyncio.run(_run_seed_primitives(catalog=args.catalog))
    parser.error(f"Unknown command: {args.command}")  # pragma: no cover
    return 2


if __name__ == "__main__":
    sys.exit(main())
