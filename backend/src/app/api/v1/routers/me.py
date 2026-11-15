"""Material listing needed by sharing."""

from typing import Literal

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import MaterialQueryServiceDep
from src.app.contracts.documents import MaterialRole
from src.app.schemas.me import MaterialOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/materials", response_model=list[MaterialOut], status_code=200, operation_id="me_materials")
async def list_materials(
    user: CurrentUserDep,
    service: MaterialQueryServiceDep,
    filter: Literal["mine", "shared"] = "mine",
) -> list[MaterialOut]:
    role = MaterialRole.OWNER if filter == "mine" else MaterialRole.SHARED
    records = await service.list_materials(user.id, role)
    result = []
    for record in records:
        source_type = (
            "gdocs"
            if record.source_type == "gdocs"
            else (
                "pdf"
                if record.mime_type == "application/pdf"
                else "docx"
                if record.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                else "md"
            )
        )
        result.append(
            MaterialOut(
                document_id=record.document_id,
                title=record.title,
                source_type=source_type,
                status=record.status,
                role=role.value,
                shared_by_email=record.shared_by_email,
                parts_total=record.parts_total,
                parts_published=record.parts_published,
                parts_failed=record.parts_failed,
                updated_at=record.updated_at,
            )
        )
    return result
