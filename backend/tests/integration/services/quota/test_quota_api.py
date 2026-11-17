"""Quota period boundaries exposed by the authenticated HTTP API."""

from collections.abc import Iterator
from datetime import date
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.api.v1.middleware.rate_limit import limiter
from src.app.bootstrap.container import ApplicationContainer
from src.app.models.user import User
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.quota.quota_ledger import QuotaLedger
from src.main import create_app
from tests.support.fakes.core.clock import FixedClock

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Iterator[TestClient]:
    limiter.reset()
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        container = cast(ApplicationContainer, cast(FastAPI, test_client.app).state.container)
        container.__dict__["quota_ledger"] = QuotaLedger(
            users_factory=UserRepository,
            ledger_factory=GenerationLedgerRepository,
            parts_factory=DocumentPartRepository,
            clock=FixedClock(date(2024, 2, 29)),
        )
        yield test_client


async def test_me_quota_reports_anchored_leap_period(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": "quota-period@example.com", "password": "long-enough-password"}
    )
    assert response.status_code == 201, response.text
    user_id = UUID(response.json()["id"])
    async with session_factory() as session, session.begin():
        await session.execute(update(User).where(User.id == user_id).values(period_anchor=date(2000, 1, 31)))
    response = client.get("/api/v1/me/quota")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "monthly_limit": 20,
        "available": 20,
        "period_start": "2024-02-29",
        "period_end": "2024-03-31",
    }
