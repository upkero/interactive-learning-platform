"""Read the materials accessible to one user."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import MaterialRole
from src.app.contracts.documents.material_details import MaterialDetails
from src.app.interfaces.repositories.documents import UserMaterialRepositoryProtocol


class MaterialQueryService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        materials: Callable[[AsyncSession], UserMaterialRepositoryProtocol],
    ) -> None:
        self._session_factory = session_factory
        self._materials = materials

    async def list_materials(self, user_id: UUID, role: MaterialRole) -> list[MaterialDetails]:
        async with self._session_factory() as session:
            return await self._materials(session).list_details(user_id, role)
