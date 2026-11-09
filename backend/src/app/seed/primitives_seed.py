"""Seeding of the primitives catalog (mirrors of @grasp/primitives)."""

import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.repositories.primitive_repository import PrimitiveRepository

# backend/src/app/seed -> backend -> repo root; the published catalog of
# the @grasp/primitives workspace lives next to the backend package.
_REPO_ROOT: Path = Path(__file__).resolve().parents[4]
_BACKEND_ROOT: Path = Path(__file__).resolve().parents[3]

# Candidate locations of the published primitives catalog, in order.
DEFAULT_CATALOG_CANDIDATES: tuple[Path, ...] = (
    # The resource is included in the backend image and committed locally.
    _BACKEND_ROOT / "resources" / "catalog.json",
    # Volume mounted by the seed service in infra/compose.yml
    Path("/app/primitives-dist/catalog.json"),
    # Local run from any working directory
    _REPO_ROOT / "primitives" / "dist" / "catalog.json",
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
    catalog: Any = json.loads(payload)
    if (
        not isinstance(catalog, dict)
        or type(catalog.get("catalogVersion")) is not int
        or catalog["catalogVersion"] != 1
        or not isinstance(catalog.get("primitives"), list)
    ):
        raise ValueError("Invalid primitives catalog: expected catalogVersion 1 and a primitives array")
    items: list[dict[str, Any]] = catalog["primitives"]
    for index, item in enumerate(items):
        if (
            not isinstance(item, dict)
            or not all(isinstance(item.get(key), str) and item[key] for key in ("id", "version", "description"))
            or not isinstance(item.get("modes"), list)
            or not all(isinstance(mode, str) for mode in item["modes"])
            or not isinstance(item.get("paramsSchema"), dict)
        ):
            raise ValueError(f"Invalid primitives catalog: invalid primitive at index {index}")
    repository = PrimitiveRepository(session)
    for item in items:
        await repository.upsert(
            primitive_id=item["id"],
            version=item["version"],
            description=item["description"],
            modes=list(item["modes"]),
            params_schema=dict(item["paramsSchema"]),
        )
    return len(items)
