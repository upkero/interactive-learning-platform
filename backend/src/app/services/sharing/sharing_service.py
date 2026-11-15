"""Grant registered users shared access to owned materials."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
        session: AsyncSession,
        materials: UserMaterialRepositoryProtocol,
        users: UserRepositoryProtocol,
    ) -> None:
        self._session = session
        self._materials = materials
        self._users = users

    async def share(self, *, owner_id: UUID, document_id: UUID, email: str) -> None:
        if await self._materials.get_role(owner_id, document_id) is not MaterialRole.OWNER:
            raise DocumentNotFoundError()
        recipient = await self._users.get_by_email(email.strip().lower())
        if recipient is None:
            raise RecipientNotRegisteredError()
        if recipient.id == owner_id:
            raise ShareWithSelfError()
        try:
            await self._materials.share_if_absent(recipient.id, document_id, owner_id)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        logger.info("material.shared document_id=%s recipient_id=%s", document_id, recipient.id)
