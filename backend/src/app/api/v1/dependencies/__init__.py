"""FastAPI dependencies, split into files by domain: each sub-module imports only what its domain needs."""

from src.app.api.v1.dependencies.auth import AuthServiceDep, CurrentUserDep, get_auth_service, get_current_user
from src.app.api.v1.dependencies.container import ContainerDep, get_container
from src.app.api.v1.dependencies.db import DBSessionDep, get_db_session
from src.app.api.v1.dependencies.documents import ImageUrlResolverDep, get_image_url_resolver
from src.app.api.v1.dependencies.llm import LLMClientDep, get_llm_client
from src.app.api.v1.dependencies.services import (
    DocumentQueryServiceDep,
    FileInspectorDep,
    TaskDispatcherDep,
    UploadServiceDep,
    get_document_query_service,
    get_file_inspector,
    get_task_dispatcher,
    get_upload_service,
)
from src.app.api.v1.dependencies.storage import ObjectStorageClientDep, get_object_storage

__all__ = [
    "AuthServiceDep",
    "ContainerDep",
    "CurrentUserDep",
    "DBSessionDep",
    "DocumentQueryServiceDep",
    "FileInspectorDep",
    "ImageUrlResolverDep",
    "LLMClientDep",
    "ObjectStorageClientDep",
    "TaskDispatcherDep",
    "UploadServiceDep",
    "get_auth_service",
    "get_container",
    "get_current_user",
    "get_db_session",
    "get_document_query_service",
    "get_file_inspector",
    "get_image_url_resolver",
    "get_llm_client",
    "get_object_storage",
    "get_task_dispatcher",
    "get_upload_service",
]
