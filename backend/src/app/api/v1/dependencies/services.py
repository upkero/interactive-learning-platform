"""Annotated dependencies of the API services (story 1.4).

Every service is built once per application in ``ApplicationContainer``
and injected here; routers never assemble repositories or settings.
"""

from typing import Annotated

from fastapi import Depends

from src.app.api.v1.dependencies.container import ContainerDep
from src.app.services.documents.document_query_service import DocumentQueryService
from src.app.services.documents.generation_service import GenerationService
from src.app.services.documents.import_service import ImportService
from src.app.services.documents.material_query_service import MaterialQueryService
from src.app.services.documents.part_query_service import PartQueryService
from src.app.services.documents.quiz_check_service import QuizCheckService
from src.app.services.documents.upload_service import UploadService
from src.app.services.quota.quota_service import QuotaService
from src.app.services.reports.report_service import ReportService
from src.app.services.sharing.sharing_service import SharingService
from src.app.services.users.profile_service import ProfileService


def get_upload_service(container: ContainerDep) -> UploadService:
    return container.upload_service


UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]


def get_import_service(container: ContainerDep) -> ImportService:
    return container.import_service


ImportServiceDep = Annotated[ImportService, Depends(get_import_service)]


def get_document_query_service(container: ContainerDep) -> DocumentQueryService:
    return container.document_query_service


DocumentQueryServiceDep = Annotated[DocumentQueryService, Depends(get_document_query_service)]


def get_generation_service(container: ContainerDep) -> GenerationService:
    return container.generation_service


GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]


def get_part_query_service(container: ContainerDep) -> PartQueryService:
    return container.part_query_service


PartQueryServiceDep = Annotated[PartQueryService, Depends(get_part_query_service)]


def get_quiz_check_service(container: ContainerDep) -> QuizCheckService:
    return container.quiz_check_service


QuizCheckServiceDep = Annotated[QuizCheckService, Depends(get_quiz_check_service)]


def get_report_service(container: ContainerDep) -> ReportService:
    return container.report_service


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


def get_sharing_service(container: ContainerDep) -> SharingService:
    return container.sharing_service


SharingServiceDep = Annotated[SharingService, Depends(get_sharing_service)]


def get_material_query_service(container: ContainerDep) -> MaterialQueryService:
    return container.material_query_service


MaterialQueryServiceDep = Annotated[MaterialQueryService, Depends(get_material_query_service)]


def get_profile_service(container: ContainerDep) -> ProfileService:
    return container.profile_service


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


def get_quota_service(container: ContainerDep) -> QuotaService:
    return container.quota_service


QuotaServiceDep = Annotated[QuotaService, Depends(get_quota_service)]


__all__ = [
    "DocumentQueryServiceDep",
    "GenerationServiceDep",
    "ImportServiceDep",
    "MaterialQueryServiceDep",
    "PartQueryServiceDep",
    "ProfileServiceDep",
    "QuizCheckServiceDep",
    "QuotaServiceDep",
    "ReportServiceDep",
    "SharingServiceDep",
    "UploadServiceDep",
]
