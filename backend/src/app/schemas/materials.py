"""Material sharing schemas."""

from uuid import UUID

from pydantic import BaseModel, EmailStr


class ShareMaterialRequest(BaseModel):
    document_id: UUID
    email: EmailStr


class ShareMaterialResponse(BaseModel):
    status: str = "ok"
