"""HTTP endpoint for published and in-progress parts."""

from uuid import UUID

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import PartQueryServiceDep
from src.app.api.v1.responses import error_responses
from src.app.schemas.parts import PartContentOut, PartOut

router = APIRouter(prefix="/parts", tags=["parts"])


@router.get(
    "/{part_id}",
    response_model=PartOut,
    status_code=200,
    operation_id="parts_get",
    responses=error_responses(401, 404, 422, 500),
)
async def get_part(part_id: UUID, user: CurrentUserDep, service: PartQueryServiceDep) -> PartOut:
    details = await service.get(user_id=user.id, part_id=part_id)
    part = details.part
    return PartOut(
        id=part.id,
        document_id=part.document_id,
        title=part.title,
        index=part.index,
        status=part.status.value,
        content=PartContentOut.model_validate(details.content) if details.content is not None else None,
    )
