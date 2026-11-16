"""Repository of user materials (access rights)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents.material_details import MaterialDetails
from src.app.contracts.documents.material_record import MaterialRecord
from src.app.contracts.documents.shared_user_info import SharedUserInfo
from src.app.contracts.documents.statuses import MaterialRole
from src.app.exceptions.documents import DocumentsIntegrityError, MaterialAccessDuplicateError
from src.app.interfaces.repositories.documents import UserMaterialRepositoryProtocol
from src.app.models.document import Document
from src.app.models.document_part import DocumentPart
from src.app.models.user import User
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

    async def share_if_absent(self, user_id: UUID, document_id: UUID, shared_by: UUID) -> None:
        statement = (
            insert(UserMaterial)
            .values(
                user_id=user_id,
                document_id=document_id,
                role=MaterialRole.SHARED.value,
                shared_by=shared_by,
            )
            .on_conflict_do_nothing(index_elements=[UserMaterial.user_id, UserMaterial.document_id])
        )
        await self._session.execute(statement)

    async def list_details(self, user_id: UUID, role: MaterialRole) -> list[MaterialDetails]:
        stmt = (
            select(
                Document,
                UserMaterial.role,
                User.email,
                func.count(DocumentPart.id),
                func.count(DocumentPart.id).filter(DocumentPart.status == "published"),
                func.count(DocumentPart.id).filter(DocumentPart.status == "failed"),
            )
            .join(UserMaterial, UserMaterial.document_id == Document.id)
            .outerjoin(User, User.id == UserMaterial.shared_by)
            .outerjoin(DocumentPart, DocumentPart.document_id == Document.id)
            .where(UserMaterial.user_id == user_id, UserMaterial.role == role.value)
            .group_by(Document.id, UserMaterial.role, User.email)
            .order_by(Document.updated_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            MaterialDetails(
                document_id=doc.id,
                title=doc.title,
                source_type=doc.source_type,
                mime_type=doc.mime_type,
                status=doc.status,
                role=material_role,
                shared_by_email=email,
                parts_total=total,
                parts_published=published,
                parts_failed=failed,
                updated_at=doc.updated_at,
            )
            for doc, material_role, email, total, published, failed in rows
        ]

    async def list_shared_with(self, document_id: UUID) -> list[SharedUserInfo]:
        """Users with the shared role on the document, oldest share first."""
        stmt = (
            select(UserMaterial, User.email, User.display_name)
            .join(User, User.id == UserMaterial.user_id)
            .where(UserMaterial.document_id == document_id, UserMaterial.role == MaterialRole.SHARED.value)
            .order_by(UserMaterial.created_at)
        )
        rows = await self._session.execute(stmt)
        return [
            SharedUserInfo(
                user_id=material.user_id,
                email=email,
                display_name=display_name,
                shared_at=material.created_at,
            )
            for material, email, display_name in rows.all()
        ]
