"""Profile, quota and material listing endpoints (stories 1.4.11, 1.4.14)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import (
    MaterialQueryServiceDep,
    ProfileServiceDep,
    QuotaServiceDep,
)
from src.app.api.v1.responses import error_responses
from src.app.contracts.documents import MaterialRole
from src.app.contracts.users import UserRecord
from src.app.contracts.users.profile_update import ProfileUpdate
from src.app.schemas.me import LastAnswersOut, MaterialOut, MeOut, MePatch, QuotaOut

router = APIRouter(prefix="/me", tags=["me"])


def _me(user: UserRecord) -> MeOut:
    answers = user.profile.get("last_answers")
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        notify_email=user.notify_email,
        last_answers=LastAnswersOut.model_validate(answers) if answers else None,
    )


@router.get("", response_model=MeOut, status_code=200, operation_id="me_get", responses=error_responses(401, 500))
async def get_me(user: CurrentUserDep) -> MeOut:
    return _me(user)


@router.patch(
    "", response_model=MeOut, status_code=200, operation_id="me_patch", responses=error_responses(401, 422, 500)
)
async def patch_me(body: MePatch, user: CurrentUserDep, service: ProfileServiceDep) -> MeOut:
    command = ProfileUpdate(
        provided=frozenset(body.model_fields_set),
        display_name=body.display_name,
        locale=body.locale,
        notify_email=body.notify_email,
    )
    return _me(await service.update(user.id, command))


@router.get(
    "/quota", response_model=QuotaOut, status_code=200, operation_id="me_quota", responses=error_responses(401, 500)
)
async def get_quota(user: CurrentUserDep, service: QuotaServiceDep) -> QuotaOut:
    state = await service.current(user.id)
    return QuotaOut(
        monthly_limit=state.monthly_limit,
        available=state.available,
        period_start=state.period.start,
        period_end=state.period.end,
    )


@router.get(
    "/materials",
    response_model=list[MaterialOut],
    status_code=200,
    operation_id="me_materials",
    responses=error_responses(401, 422, 500),
)
async def list_materials(
    user: CurrentUserDep,
    service: MaterialQueryServiceDep,
    role_filter: Annotated[Literal["mine", "shared"], Query(alias="filter")] = "mine",
) -> list[MaterialOut]:
    role = MaterialRole.OWNER if role_filter == "mine" else MaterialRole.SHARED
    records = await service.list_materials(user.id, role)
    return [
        MaterialOut(
            document_id=record.document_id,
            title=record.title,
            source_type=record.source_kind,
            status=record.status,
            role=role.value,
            shared_by_email=record.shared_by_email,
            parts_total=record.parts_total,
            parts_published=record.parts_published,
            parts_failed=record.parts_failed,
            updated_at=record.updated_at,
        )
        for record in records
    ]
