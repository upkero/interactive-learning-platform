"""Seeding of the primitives catalog (mirrors of @grasp/primitives)."""

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.repositories.primitive_repository import PrimitiveRepository

_BACKEND_ROOT: Path = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = _BACKEND_ROOT / "resources" / "catalog.json"


class CatalogPrimitive(BaseModel):
    """The fields consumed by the seeder from a TypeScript catalog entry."""

    model_config = ConfigDict(strict=True)

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    modes: list[str]
    params_schema: dict[str, Any] = Field(alias="paramsSchema")


class CatalogFile(BaseModel):
    """Versioned object exported by @grasp/primitives."""

    model_config = ConfigDict(strict=True)

    catalog_version: int = Field(alias="catalogVersion")
    primitives: list[CatalogPrimitive]

    @field_validator("catalog_version")
    @classmethod
    def supported_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("only catalogVersion 1 is supported")
        return value


def resolve_catalog_path(explicit: Path | str | None) -> Path:
    """Return an explicit path or the catalog included in backend resources."""
    path = Path(explicit) if explicit is not None else DEFAULT_CATALOG_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Primitives catalog not found: {path}")
    return path


def _describe_validation_error(exc: ValidationError) -> str:
    """Collapse pydantic errors into one line: ``loc: msg; loc: msg``."""
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        details.append(f"{location}: {error['msg']}" if location else error["msg"])
    return "; ".join(details)


async def load_catalog(catalog_path: Path) -> CatalogFile:
    """Read and validate the catalog file.

    Raises OSError if the file cannot be read and ValueError with a one-line
    message if it is not a valid catalog (including invalid JSON or UTF-8).
    """
    payload = await asyncio.to_thread(catalog_path.read_bytes)
    try:
        return CatalogFile.model_validate_json(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid primitives catalog: {_describe_validation_error(exc)}") from exc


async def seed_primitives_from_catalog(session: AsyncSession, catalog_path: Path) -> int:
    """Load the catalog file and upsert its primitives; return items count."""
    return await seed_primitives(session, await load_catalog(catalog_path))


async def seed_primitives(session: AsyncSession, catalog: CatalogFile) -> int:
    """Upsert every primitive from a validated catalog; return items count."""
    repository = PrimitiveRepository(session)
    for item in catalog.primitives:
        await repository.upsert(
            primitive_id=item.id,
            version=item.version,
            description=item.description,
            modes=item.modes,
            params_schema=item.params_schema,
        )
    return len(catalog.primitives)
