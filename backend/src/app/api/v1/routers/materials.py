"""Material sharing endpoint."""

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import SharingServiceDep
from src.app.schemas.materials import ShareMaterialIn, ShareMaterialOut

router = APIRouter(prefix="/materials", tags=["materials"])


@router.post("/share", response_model=ShareMaterialOut, status_code=200, operation_id="materials_share")
async def share_material(body: ShareMaterialIn, user: CurrentUserDep, service: SharingServiceDep) -> ShareMaterialOut:
    await service.share(owner_id=user.id, document_id=body.document_id, email=body.email)
    return ShareMaterialOut()
