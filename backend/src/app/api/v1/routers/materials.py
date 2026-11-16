"""Material sharing endpoint."""

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import SharingServiceDep
from src.app.api.v1.responses import error_responses
from src.app.schemas.materials import ShareMaterialRequest, ShareMaterialResponse

router = APIRouter(prefix="/materials", tags=["materials"])


@router.post(
    "/share",
    response_model=ShareMaterialResponse,
    status_code=200,
    operation_id="materials_share",
    responses=error_responses(401, 404, 422, 500),
)
async def share_material(
    body: ShareMaterialRequest, user: CurrentUserDep, service: SharingServiceDep
) -> ShareMaterialResponse:
    await service.share(owner_id=user.id, document_id=body.document_id, email=body.email)
    return ShareMaterialResponse()
