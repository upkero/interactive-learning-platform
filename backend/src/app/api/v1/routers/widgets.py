"""Widget report endpoint."""

from uuid import UUID

from fastapi import APIRouter

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import ReportServiceDep
from src.app.api.v1.responses import error_responses
from src.app.contracts.widgets import ReportReason
from src.app.schemas.widgets import WidgetReportRequest, WidgetReportResponse

router = APIRouter(prefix="/widgets", tags=["widgets"])


@router.post(
    "/{widget_id}/reports",
    response_model=WidgetReportResponse,
    status_code=200,
    operation_id="widgets_report",
    responses=error_responses(401, 404, 422, 500),
)
async def report_widget(
    widget_id: UUID,
    body: WidgetReportRequest,
    user: CurrentUserDep,
    service: ReportServiceDep,
) -> WidgetReportResponse:
    await service.report(
        user_id=user.id,
        widget_id=widget_id,
        part_id=body.part_id,
        reason=ReportReason(body.reason),
        comment=body.comment,
    )
    return WidgetReportResponse()
