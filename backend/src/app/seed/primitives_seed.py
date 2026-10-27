"""Seeding of the primitives catalog (mirrors of @grasp/primitives)."""

import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.repositories.primitive_repository import PrimitiveRepository

# Candidate locations of the published primitives catalog, in order.
DEFAULT_CATALOG_CANDIDATES: tuple[Path, ...] = (
    Path("/app/primitives-dist/catalog.json"),
    Path("../primitives/dist/catalog.json"),
)


def resolve_catalog_path(explicit: Path | str | None) -> Path:
    """Return the catalog path: explicit argument or first existing default."""
    if explicit is not None:
        return Path(explicit)
    for candidate in DEFAULT_CATALOG_CANDIDATES:
        if candidate.is_file():
            return candidate
    missing = ", ".join(str(c) for c in DEFAULT_CATALOG_CANDIDATES)
    raise FileNotFoundError(f"Primitives catalog not found; build @grasp/primitives first. Looked at: {missing}")


async def seed_primitives_from_catalog(session: AsyncSession, catalog_path: Path) -> int:
    """Upsert every primitive from the catalog file; return items count."""
    payload = await asyncio.to_thread(catalog_path.read_text, encoding="utf-8")
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
