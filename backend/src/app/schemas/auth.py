"""HTTP schemas of the auth area (story 1.4.2).

They live only at the HTTP boundary: the router converts them into
service calls, and service results (``UserRecord``) into responses.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="At least 8 characters.")
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthUserOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    locale: str
    created_at: datetime


class SessionStatusOut(BaseModel):
    status: Literal["ok"]
