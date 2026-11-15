"""Read the materials accessible to one user."""

from uuid import UUID

from src.app.contracts.documents import MaterialRole
from src.app.contracts.documents.material_details import MaterialDetails
from src.app.interfaces.repositories.documents import UserMaterialRepositoryProtocol


class MaterialQueryService:
    def __init__(self, materials: UserMaterialRepositoryProtocol) -> None:
        self._materials = materials

    async def list_materials(self, user_id: UUID, role: MaterialRole) -> list[MaterialDetails]:
        return await self._materials.list_details(user_id, role)
