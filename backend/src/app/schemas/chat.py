from pydantic import BaseModel, Field


class MessageSchema(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: list[MessageSchema] = Field(..., min_length=1)


class ChatResponse(BaseModel):
    content: str
    model: str | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
