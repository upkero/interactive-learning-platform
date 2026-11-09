"""Validate published JSON schemas and the non-empty generated example catalog."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.seed.primitives_seed import seed_primitives_from_catalog

BACKEND = Path(__file__).resolve().parents[2]
CATALOGS = (
    BACKEND / "resources" / "catalog.json",
    BACKEND / "tests" / "support" / "fixtures" / "seed" / "three-frame-catalog.json",
)


@pytest.mark.unit
@pytest.mark.parametrize("catalog_path", CATALOGS)
def test_catalog_schemas_and_examples(catalog_path: Path) -> None:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog_path == CATALOGS[1]:
        assert catalog["primitives"]  # the production registry is currently empty
    for primitive in catalog["primitives"]:
        schema = primitive["paramsSchema"]
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        assert primitive["examples"]
        for example in primitive["examples"]:
            validator.validate(example["params"])


@pytest.mark.unit
def test_generated_schema_rejects_out_of_range_input() -> None:
    catalog = json.loads(CATALOGS[1].read_text(encoding="utf-8"))
    validator = Draft202012Validator(catalog["primitives"][0]["paramsSchema"])
    assert not validator.is_valid({"left": -1})
    assert validator.is_valid({"left": 2})  # `right` has a default


@pytest.mark.unit
async def test_empty_catalog_and_invalid_formats(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    session = AsyncMock(spec=AsyncSession)
    path.write_text('{"catalogVersion": 1, "primitives": []}', encoding="utf-8")
    with patch("src.app.seed.primitives_seed.PrimitiveRepository") as repository:
        assert await seed_primitives_from_catalog(session, path) == 0
        repository.return_value.upsert.assert_not_called()
    invalid_payloads: list[Any] = [
        [],
        {},
        {"primitives": []},
        {"catalogVersion": 2, "primitives": []},
        {"catalogVersion": 1, "primitives": {}},
        {"catalogVersion": 1, "primitives": [{}]},
    ]
    for payload in invalid_payloads:
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid primitives catalog"):
            await seed_primitives_from_catalog(session, path)


@pytest.mark.unit
async def test_maps_camel_case_schema_to_repository(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    fixture: dict[str, Any] = json.loads(CATALOGS[1].read_text(encoding="utf-8"))
    path.write_text(json.dumps(fixture), encoding="utf-8")
    session = AsyncMock(spec=AsyncSession)
    with patch("src.app.seed.primitives_seed.PrimitiveRepository") as repository:
        repository.return_value.upsert = AsyncMock()
        assert await seed_primitives_from_catalog(session, path) == 1
        item = fixture["primitives"][0]
        repository.return_value.upsert.assert_awaited_once_with(
            primitive_id=item["id"],
            version=item["version"],
            description=item["description"],
            modes=item["modes"],
            params_schema=item["paramsSchema"],
        )


@pytest.mark.unit
async def test_development_seed_fixture_uses_catalog_format() -> None:
    fixture = BACKEND / "tests" / "support" / "fixtures" / "seed" / "primitives.json"
    session = AsyncMock(spec=AsyncSession)
    with patch("src.app.seed.primitives_seed.PrimitiveRepository") as repository:
        repository.return_value.upsert = AsyncMock()
        assert await seed_primitives_from_catalog(session, fixture) == 5
        assert repository.return_value.upsert.await_count == 5
