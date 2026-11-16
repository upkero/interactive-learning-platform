"""Document endpoints: upload (1.4.3) and read (1.4.3+).

The router is a thin adapter: it converts schemas into service calls
and service contracts into response schemas. Domain errors are not
caught here — the exception handlers (1.4.1) turn them into the unified
error format.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, UploadFile

from src.app.api.v1.dependencies.auth import CurrentUserDep
from src.app.api.v1.dependencies.services import (
    DocumentQueryServiceDep,
    GenerationServiceDep,
    ImportServiceDep,
    UploadServiceDep,
)
from src.app.api.v1.responses import error_responses
from src.app.contracts.documents import DocumentDetails, TopicNode
from src.app.contracts.documents.generation import GenerationAnswers, GenerationCommand
from src.app.schemas.documents import (
    DocumentCreatedOut,
    DocumentImportRequest,
    DocumentOut,
    GenerateRequest,
    GenerateResponse,
    PartSummaryOut,
    PlannedPartOut,
    PlanRequest,
    PlanResponse,
    SharedWithOut,
    TopicNodeOut,
    TopicTreeOut,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    status_code=201,
    response_model=DocumentCreatedOut,
    operation_id="documents_upload",
    responses=error_responses(401, 413, 415, 422, 429, 500, 503),
)
async def upload_document(
    file: UploadFile,
    user: CurrentUserDep,
    service: UploadServiceDep,
    title: Annotated[str | None, Form(max_length=200)] = None,
) -> DocumentCreatedOut:
    document = await service.upload(
        owner_id=user.id,
        filename=file.filename,
        title=title,
        stream=file,
    )
    return DocumentCreatedOut(id=document.id, status=document.status.value)


@router.post(
    "/import",
    status_code=201,
    response_model=DocumentCreatedOut,
    operation_id="documents_import",
    responses=error_responses(401, 422, 429, 500, 503),
)
async def import_document(
    body: DocumentImportRequest,
    user: CurrentUserDep,
    service: ImportServiceDep,
) -> DocumentCreatedOut:
    document = await service.import_document(owner_id=user.id, url=body.url)
    return DocumentCreatedOut(id=document.id, status=document.status.value)


@router.get(
    "/{document_id}/topics",
    status_code=200,
    response_model=TopicTreeOut,
    operation_id="documents_topics",
    responses=error_responses(401, 404, 409, 422, 500),
)
async def get_document_topics(
    document_id: UUID,
    user: CurrentUserDep,
    service: DocumentQueryServiceDep,
) -> TopicTreeOut:
    tree = await service.get_topic_tree(user_id=user.id, document_id=document_id)
    return TopicTreeOut(topics=[_topic_node(node) for node in tree])


def _topic_node(node: TopicNode) -> TopicNodeOut:
    return TopicNodeOut(
        id=node.id,
        title=node.title,
        level=node.level,
        tokens=node.total_tokens,
        children=[_topic_node(child) for child in node.children],
    )


@router.post(
    "/{document_id}/plan",
    status_code=200,
    response_model=PlanResponse,
    operation_id="documents_plan",
    responses=error_responses(401, 404, 409, 422, 500),
)
async def plan_document(
    document_id: UUID,
    body: PlanRequest,
    user: CurrentUserDep,
    service: GenerationServiceDep,
) -> PlanResponse:
    plan, available = await service.plan(user_id=user.id, document_id=document_id, topic_ids=body.topic_ids)
    return PlanResponse(
        parts=[PlannedPartOut(index=part.index, title=part.title, tokens=part.tokens) for part in plan.parts],
        cost=len(plan.parts),
        available=available,
    )


@router.post(
    "/{document_id}/generate",
    status_code=202,
    response_model=GenerateResponse,
    operation_id="documents_generate",
    responses=error_responses(401, 402, 404, 409, 422, 429, 500, 503),
)
async def generate_document(
    document_id: UUID,
    body: GenerateRequest,
    user: CurrentUserDep,
    service: GenerationServiceDep,
) -> GenerateResponse:
    started = await service.start(
        GenerationCommand(
            user_id=user.id,
            document_id=document_id,
            topic_ids=tuple(body.topic_ids),
            answers=GenerationAnswers(level=body.answers.level, goal=body.answers.goal, depth=body.answers.depth),
        )
    )
    return GenerateResponse(
        document_id=started.document_id,
        part_ids=list(started.part_ids),
        cost=started.cost,
        available=started.available,
    )


@router.get(
    "/{document_id}",
    status_code=200,
    response_model=DocumentOut,
    operation_id="documents_get",
    responses=error_responses(401, 404, 422, 500),
)
async def get_document(
    document_id: UUID,
    user: CurrentUserDep,
    service: DocumentQueryServiceDep,
) -> DocumentOut:
    details: DocumentDetails = await service.get_document(user_id=user.id, document_id=document_id)
    document = details.document
    return DocumentOut(
        id=document.id,
        title=document.title,
        status=document.status.value,
        error_code=document.error_code,
        page_count=document.page_count,
        role=details.role.value,
        source_url=details.source_url,
        parts=[
            PartSummaryOut(id=part.id, index=part.index, title=part.title, status=part.status.value)
            for part in details.parts
        ],
        shared_with=[
            SharedWithOut(
                display_name=shared.display_name,
                email=shared.email,
                shared_at=shared.shared_at,
            )
            for shared in details.shared_with
        ],
    )


__all__ = ["router"]
