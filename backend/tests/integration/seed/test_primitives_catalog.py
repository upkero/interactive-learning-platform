"""Seed both the production catalog and generated test fixture into Postgres."""

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from src.app.models.primitive import Primitive
from src.app.seed.primitives_seed import seed_primitives_from_catalog
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration
BACKEND = Path(__file__).resolve().parents[3]


async def test_catalog_seed_is_idempotent(session_factory: SessionFactory) -> None:
    production = BACKEND / "resources" / "catalog.json"
    fixture = BACKEND / "tests" / "support" / "fixtures" / "seed" / "three-frame-catalog.json"
    for path in (production, fixture):
        catalog = json.loads(path.read_text(encoding="utf-8"))
        async with session_factory() as session, session.begin():
            assert await seed_primitives_from_catalog(session, path) == len(catalog["primitives"])
            for item in catalog["primitives"]:
                row = await session.get(Primitive, item["id"])
                assert row is not None
                row.params_schema = {"type": "null"}
            await session.flush()
            assert await seed_primitives_from_catalog(session, path) == len(catalog["primitives"])
        async with session_factory() as session:
            for item in catalog["primitives"]:
                row = await session.get(Primitive, item["id"])
                assert row is not None
                assert row.params_schema == item["paramsSchema"]
    async with session_factory() as session:
        ids = {item["id"] for path in (production, fixture) for item in json.loads(path.read_text())["primitives"]}
        assert await session.scalar(select(func.count()).select_from(Primitive)) == len(ids)
