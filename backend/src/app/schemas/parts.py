"""Public response schemas for document parts; quiz solutions never belong here."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Discriminator, Field, JsonValue, Tag


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChoiceOption(PublicModel):
    id: str
    text: str


class ChoiceQuiz(PublicModel):
    key: str
    ref: str
    type: Literal["single_choice", "multiple_choice"]
    prompt: str
    options: list[ChoiceOption]


class OrderingQuiz(PublicModel):
    key: str
    ref: str
    type: Literal["ordering"]
    prompt: str
    items: list[ChoiceOption]


class NumericQuiz(PublicModel):
    key: str
    ref: str
    type: Literal["numeric"]
    prompt: str
    unit: str | None = None


QuizOut = Annotated[ChoiceQuiz | OrderingQuiz | NumericQuiz, Field(discriminator="type")]


class ImageFallback(PublicModel):
    type: Literal["image"]
    image_id: str


class TextFallback(PublicModel):
    type: Literal["text"]
    text: str


Fallback = Annotated[ImageFallback | TextFallback, Field(discriminator="type")]


class ConfigWidget(PublicModel):
    status: Literal["ready"]
    kind: Literal["config"]
    widget_id: UUID
    title: str
    primitive_id: str
    mode: str
    params: dict[str, JsonValue]


class CodeWidget(PublicModel):
    status: Literal["ready"]
    kind: Literal["code"]
    widget_id: UUID
    title: str
    labels: dict[str, str] = Field(default_factory=dict)
    compiled_js: str | None = None


class PendingWidget(PublicModel):
    status: Literal["pending", "fallback"]
    title: str
    fallback: Fallback


def _widget_variant(value: object) -> str | None:
    if isinstance(value, dict):
        status, kind = value.get("status"), value.get("kind")
    else:
        status, kind = getattr(value, "status", None), getattr(value, "kind", None)
    if status == "ready":
        return str(kind)
    if status in ("pending", "fallback"):
        return "pending"
    return None


WidgetOut = Annotated[
    Annotated[ConfigWidget, Tag("config")]
    | Annotated[CodeWidget, Tag("code")]
    | Annotated[PendingWidget, Tag("pending")],
    Discriminator(_widget_variant),
]


class ImageOut(PublicModel):
    image_id: UUID
    caption: str | None = None
    url: str | None = None


class SourceSpan(PublicModel):
    start: int
    end: int


class SectionOut(PublicModel):
    title: str
    anchor: str
    topic_id: str | None
    source_span: SourceSpan | None
    page: int | None = None


class PartContentOut(PublicModel):
    schema_version: Literal[1] = 1
    title: str
    markdown: str
    key_terms: list[str] = Field(default_factory=list)
    widgets: dict[str, WidgetOut] = Field(default_factory=dict)
    images: dict[str, ImageOut] = Field(default_factory=dict)
    quizzes: list[QuizOut] = Field(default_factory=list)
    sources: dict[str, SourceSpan] = Field(default_factory=dict)
    sections: list[SectionOut] = Field(default_factory=list)


class PartOut(BaseModel):
    id: UUID
    document_id: UUID
    title: str
    index: int
    status: Literal["queued", "main_pass", "resolving", "assembling", "published", "failed"]
    content: PartContentOut | None
