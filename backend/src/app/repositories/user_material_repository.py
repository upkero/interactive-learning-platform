"""Repository of user materials (access rights)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.material_record import MaterialRecord
from src.app.contracts.documents.statuses import MaterialRole
from src.app.exceptions.documents import DocumentsIntegrityError, MaterialAccessDuplicateError
from src.app.interfaces.repositories.documents import UserMaterialRepositoryProtocol
from src.app.models.user_material import UserMaterial
from src.app.repositories._errors import constraint_name

USER_MATERIAL_PRIMARY_KEY: str = "pk_user_materials"


class UserMaterialRepository(UserMaterialRepositoryProtocol):
    """Access to the user_materials table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: UserMaterial) -> MaterialRecord:
        return MaterialRecord(
            user_id=row.user_id,
            document_id=row.document_id,
            role=MaterialRole(row.role),
            shared_by=row.shared_by,
            created_at=row.created_at,
        )

    async def get_role(self, user_id: UUID, document_id: UUID) -> MaterialRole | None:
        row = await self._session.get(UserMaterial, (user_id, document_id))
        return MaterialRole(row.role) if row is not None else None

    async def create(
        self,
        *,
        user_id: UUID,
        document_id: UUID,
        role: MaterialRole,
        shared_by: UUID | None = None,
    ) -> MaterialRecord:
        row = UserMaterial(user_id=user_id, document_id=document_id, role=role.value, shared_by=shared_by)
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if constraint_name(exc) == USER_MATERIAL_PRIMARY_KEY:
                raise MaterialAccessDuplicateError from exc
            raise DocumentsIntegrityError from exc
        return self._to_record(row)

    async def list_by_user(self, user_id: UUID) -> list[MaterialRecord]:
        rows = await self._session.scalars(select(UserMaterial).where(UserMaterial.user_id == user_id))
        return [self._to_record(row) for row in rows.all()]
