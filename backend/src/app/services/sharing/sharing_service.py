"""Grant registered users shared access to owned materials."""

import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import MaterialRole
from src.app.exceptions.documents import DocumentNotFoundError
from src.app.exceptions.sharing import RecipientNotRegisteredError, ShareWithSelfError
from src.app.interfaces.repositories.documents import UserMaterialRepositoryProtocol
from src.app.interfaces.repositories.users import UserRepositoryProtocol

logger = logging.getLogger(__name__)


class SharingService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        materials: Callable[[AsyncSession], UserMaterialRepositoryProtocol],
        users: Callable[[AsyncSession], UserRepositoryProtocol],
    ) -> None:
        self._session_factory = session_factory
        self._materials = materials
        self._users = users

    async def share(self, *, owner_id: UUID, document_id: UUID, email: str) -> None:
        async with self._session_factory() as session, session.begin():
            materials = self._materials(session)
            if await materials.get_role(owner_id, document_id) is not MaterialRole.OWNER:
                raise DocumentNotFoundError()
            recipient = await self._users(session).get_by_email(email.strip().lower())
            if recipient is None:
                raise RecipientNotRegisteredError()
            if recipient.id == owner_id:
                raise ShareWithSelfError()
            await materials.share_if_absent(recipient.id, document_id, owner_id)
        logger.info("Material shared.", extra={"document_id": str(document_id), "recipient_id": str(recipient.id)})
