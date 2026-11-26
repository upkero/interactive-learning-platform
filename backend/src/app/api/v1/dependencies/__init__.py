"""FastAPI dependencies, split into files by domain: each sub-module imports only what its domain needs."""

from src.app.api.v1.dependencies.auth import AuthServiceDep, CurrentUserDep, get_auth_service, get_current_user
from src.app.api.v1.dependencies.container import ContainerDep, get_container
from src.app.api.v1.dependencies.db import DBSessionDep, get_db_session
from src.app.api.v1.dependencies.documents import ImageUrlResolverDep, get_image_url_resolver
from src.app.api.v1.dependencies.llm import LLMClientDep, get_llm_client
from src.app.api.v1.dependencies.progress import ProgressReaderDep, get_progress_reader
from src.app.api.v1.dependencies.services import (
    DocumentQueryServiceDep,
    GenerationServiceDep,
    ImportServiceDep,
    MaterialQueryServiceDep,
    PartQueryServiceDep,
    ProfileServiceDep,
    QuizCheckServiceDep,
    QuotaServiceDep,
    ReportServiceDep,
    SharingServiceDep,
    UploadServiceDep,
    get_document_query_service,
    get_generation_service,
    get_import_service,
    get_material_query_service,
    get_part_query_service,
    get_profile_service,
    get_quiz_check_service,
    get_quota_service,
    get_report_service,
    get_sharing_service,
    get_upload_service,
)
from src.app.api.v1.dependencies.storage import ObjectStorageClientDep, get_object_storage

__all__ = [
    "AuthServiceDep",
    "ContainerDep",
    "CurrentUserDep",
    "DBSessionDep",
    "DocumentQueryServiceDep",
    "GenerationServiceDep",
    "ImageUrlResolverDep",
    "ImportServiceDep",
    "LLMClientDep",
    "MaterialQueryServiceDep",
    "ObjectStorageClientDep",
    "PartQueryServiceDep",
    "ProfileServiceDep",
    "ProgressReaderDep",
    "QuizCheckServiceDep",
    "QuotaServiceDep",
    "ReportServiceDep",
    "SharingServiceDep",
    "UploadServiceDep",
    "get_auth_service",
    "get_container",
    "get_current_user",
    "get_db_session",
    "get_document_query_service",
    "get_generation_service",
    "get_image_url_resolver",
    "get_import_service",
    "get_llm_client",
    "get_material_query_service",
    "get_object_storage",
    "get_part_query_service",
    "get_profile_service",
    "get_progress_reader",
    "get_quiz_check_service",
    "get_quota_service",
    "get_report_service",
    "get_sharing_service",
    "get_upload_service",
]
