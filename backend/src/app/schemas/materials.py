"""Material sharing schemas."""

from uuid import UUID

from pydantic import BaseModel, EmailStr


class ShareMaterialIn(BaseModel):
    document_id: UUID
    email: EmailStr


class ShareMaterialOut(BaseModel):
    status: str = "ok"
