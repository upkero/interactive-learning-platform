"""Dependencies of the services used by the API (story 1.4).

Session-scoped services are built per request with their repositories
bound to the request session; cross-request collaborators (storage,
dispatcher) come from the DI container. Test doubles are injected by
overriding these getters on the app.
"""

from typing import Annotated

from fastapi import Depends

from src.app.api.v1.dependencies.container import ContainerDep
from src.app.api.v1.dependencies.db import DBSessionDep
from src.app.core.clock import SystemClock
from src.app.core.settings.upload import get_upload_settings
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.quiz_attempt_repository import QuizAttemptRepository
from src.app.repositories.report_repository import ReportRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
from src.app.services.documents.document_query_service import DocumentQueryService
from src.app.services.documents.file_inspector import FileInspector
from src.app.services.documents.generation_service import GenerationService
from src.app.services.documents.image_url_resolver import ImageUrlResolver
from src.app.services.documents.import_service import ImportService
from src.app.services.documents.part_query_service import PartQueryService
from src.app.services.documents.quiz_check_service import QuizCheckService
from src.app.services.documents.splitting import TopicTreePlanner
from src.app.services.documents.upload_service import UploadService
from src.app.services.quota.ledger import QuotaLedger
from src.app.services.reports.report_service import ReportService


def get_task_dispatcher(container: ContainerDep) -> TaskDispatcher:
    """Container-level dispatcher; tests override this with a recording fake."""
    return container.task_dispatcher


TaskDispatcherDep = Annotated[TaskDispatcher, Depends(get_task_dispatcher)]


def get_file_inspector() -> FileInspector:
    """Stateless content inspector bound to the upload settings."""
    return FileInspector(get_upload_settings())


FileInspectorDep = Annotated[FileInspector, Depends(get_file_inspector)]


def get_upload_service(
    session: DBSessionDep,
    container: ContainerDep,
    dispatcher: TaskDispatcherDep,
    inspector: FileInspectorDep,
) -> UploadService:
    return UploadService(
        session=session,
        inspector=inspector,
        storage=container.object_storage,
        dispatcher=dispatcher,
        documents=DocumentRepository(session),
        materials=UserMaterialRepository(session),
        users=UserRepository(session),
    )


UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]


def get_document_query_service(
    session: DBSessionDep,
    container: ContainerDep,
) -> DocumentQueryService:
    return DocumentQueryService(
        documents=DocumentRepository(session),
        materials=UserMaterialRepository(session),
        parts=DocumentPartRepository(session),
        storage=container.object_storage,
    )


DocumentQueryServiceDep = Annotated[DocumentQueryService, Depends(get_document_query_service)]


def get_import_service(
    session: DBSessionDep,
    dispatcher: TaskDispatcherDep,
) -> ImportService:
    return ImportService(
        session=session,
        dispatcher=dispatcher,
        documents=DocumentRepository(session),
        materials=UserMaterialRepository(session),
        users=UserRepository(session),
    )


ImportServiceDep = Annotated[ImportService, Depends(get_import_service)]


def get_generation_service(
    session: DBSessionDep,
    dispatcher: TaskDispatcherDep,
) -> GenerationService:
    return GenerationService(
        documents=DocumentRepository(session),
        materials=UserMaterialRepository(session),
        parts=DocumentPartRepository(session),
        planner=TopicTreePlanner(),
        session=session,
        users=UserRepository(session),
        dispatcher=dispatcher,
        ledger=QuotaLedger(
            users=UserRepository(session),
            ledger=GenerationLedgerRepository(session),
            clock=SystemClock(),
        ),
    )


GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]


def get_part_query_service(session: DBSessionDep, container: ContainerDep) -> PartQueryService:
    images = ImageRepository(session)
    return PartQueryService(
        parts=DocumentPartRepository(session),
        materials=UserMaterialRepository(session),
        images=images,
        resolver=ImageUrlResolver(image_repository=images, object_storage=container.object_storage),
        widgets=WidgetRepository(session),
    )


PartQueryServiceDep = Annotated[PartQueryService, Depends(get_part_query_service)]


def get_quiz_check_service(session: DBSessionDep) -> QuizCheckService:
    return QuizCheckService(
        session=session,
        parts=DocumentPartRepository(session),
        materials=UserMaterialRepository(session),
        attempts=QuizAttemptRepository(session),
    )


QuizCheckServiceDep = Annotated[QuizCheckService, Depends(get_quiz_check_service)]


def get_report_service(session: DBSessionDep) -> ReportService:
    return ReportService(session=session, reports=ReportRepository(session), usages=WidgetUsageRepository(session))


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


__all__ = [
    "DocumentQueryServiceDep",
    "FileInspectorDep",
    "GenerationServiceDep",
    "ImportServiceDep",
    "TaskDispatcherDep",
    "UploadServiceDep",
    "get_document_query_service",
    "get_file_inspector",
    "get_generation_service",
    "get_import_service",
    "get_task_dispatcher",
    "get_upload_service",
]
