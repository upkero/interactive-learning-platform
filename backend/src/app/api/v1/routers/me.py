"""Material listing needed by sharing."""

from typing import Literal

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import MaterialQueryServiceDep, ProfileServiceDep, QuotaLedgerDep
from src.app.contracts.documents import MaterialRole
from src.app.contracts.users import UserRecord
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


@router.get("", response_model=MeOut, status_code=200, operation_id="me_get")
async def get_me(user: CurrentUserDep) -> MeOut:
    return _me(user)


@router.patch("", response_model=MeOut, status_code=200, operation_id="me_patch")
async def patch_me(body: MePatch, user: CurrentUserDep, service: ProfileServiceDep) -> MeOut:
    fields = body.model_dump(exclude_unset=True)
    for key in ("locale", "notify_email"):
        if fields.get(key, True) is None:
            fields.pop(key)
    return _me(await service.update(user.id, fields))


@router.get("/quota", response_model=QuotaOut, status_code=200, operation_id="me_quota")
async def get_quota(user: CurrentUserDep, ledger: QuotaLedgerDep) -> QuotaOut:
    status = await ledger.status(user.id)
    return QuotaOut(
        monthly_limit=status.monthly_limit,
        available=status.available,
        period_start=status.period_start,
        period_end=status.period_end,
    )


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
