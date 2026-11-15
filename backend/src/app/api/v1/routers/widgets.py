"""Widget report endpoint."""

from uuid import UUID

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import ReportServiceDep
from src.app.contracts.widgets import ReportReason
from src.app.schemas.widgets import WidgetReportIn, WidgetReportOut

router = APIRouter(prefix="/widgets", tags=["widgets"])


@router.post("/{widget_id}/reports", response_model=WidgetReportOut, status_code=200, operation_id="widgets_report")
async def report_widget(
    widget_id: UUID,
    body: WidgetReportIn,
    user: CurrentUserDep,
    service: ReportServiceDep,
) -> WidgetReportOut:
    await service.report(
        user_id=user.id,
        widget_id=widget_id,
        part_id=body.part_id,
        reason=ReportReason(body.reason),
        comment=body.comment,
    )
    return WidgetReportOut()
