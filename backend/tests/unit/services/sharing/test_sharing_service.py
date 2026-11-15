"""Material sharing checks ownership and recipient identity."""

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import MaterialRole
from src.app.exceptions.documents import DocumentNotFoundError
from src.app.exceptions.sharing import RecipientNotRegisteredError, ShareWithSelfError
from src.app.services.sharing.sharing_service import SharingService
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.documents import FakeUserMaterialRepository
from tests.support.fakes.repositories.users import FakeUserRepository

pytestmark = pytest.mark.unit


async def test_share_requires_owner_and_registered_distinct_recipient() -> None:
    users, materials, session = FakeUserRepository(), FakeUserMaterialRepository(), FakeSession()
    owner = await users.create(email="owner@example.com", password_hash="hash")
    recipient = await users.create(email="recipient@example.com", password_hash="hash")
    document = uuid4()
    await materials.create(user_id=owner.id, document_id=document, role=MaterialRole.OWNER)
    service = SharingService(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: session),
        users=lambda _: users,
        materials=lambda _: materials,
    )
    with pytest.raises(DocumentNotFoundError):
        await service.share(owner_id=recipient.id, document_id=document, email=owner.email)
    with pytest.raises(RecipientNotRegisteredError):
        await service.share(owner_id=owner.id, document_id=document, email="missing@example.com")
    with pytest.raises(ShareWithSelfError):
        await service.share(owner_id=owner.id, document_id=document, email=owner.email)
    await service.share(owner_id=owner.id, document_id=document, email=" RECIPIENT@example.com ")
    await service.share(owner_id=owner.id, document_id=document, email=recipient.email)
    assert await materials.get_role(recipient.id, document) is MaterialRole.SHARED
    with pytest.raises(DocumentNotFoundError):
        await service.share(owner_id=recipient.id, document_id=document, email=owner.email)


async def test_owner_can_share_idempotently() -> None:
    users, materials, session = FakeUserRepository(), FakeUserMaterialRepository(), FakeSession()
    owner = await users.create(email="owner@example.com", password_hash="hash")
    recipient = await users.create(email="recipient@example.com", password_hash="hash")
    doc = uuid4()
    await materials.create(user_id=owner.id, document_id=doc, role=MaterialRole.OWNER)
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    service = SharingService(session_factory=factory, materials=lambda _: materials, users=lambda _: users)
    await service.share(owner_id=owner.id, document_id=doc, email="RECIPIENT@example.com")
    await service.share(owner_id=owner.id, document_id=doc, email=recipient.email)
    assert await materials.get_role(recipient.id, doc) is MaterialRole.SHARED
    assert len(await materials.list_by_user(recipient.id)) == 1
    assert session.committed == 2


async def test_sharing_rejects_missing_owner_recipient_and_self() -> None:
    users, materials, session = FakeUserRepository(), FakeUserMaterialRepository(), FakeSession()
    owner = await users.create(email="owner@example.com", password_hash="hash")
    doc = uuid4()
    await materials.create(user_id=owner.id, document_id=doc, role=MaterialRole.OWNER)
    factory = cast(async_sessionmaker[AsyncSession], lambda: session)
    service = SharingService(session_factory=factory, materials=lambda _: materials, users=lambda _: users)
    with pytest.raises(DocumentNotFoundError):
        await service.share(owner_id=uuid4(), document_id=doc, email=owner.email)
    with pytest.raises(RecipientNotRegisteredError):
        await service.share(owner_id=owner.id, document_id=doc, email="missing@example.com")
    with pytest.raises(ShareWithSelfError):
        await service.share(owner_id=owner.id, document_id=doc, email=owner.email)
    assert session.committed == 0 and session.rolled_back == 3
