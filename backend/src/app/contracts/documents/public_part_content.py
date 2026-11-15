"""Public part content contract; answer keys are intentionally absent."""

from typing import Literal, NotRequired, TypedDict

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class ChoiceOption(TypedDict):
    id: str
    text: str


class ChoiceQuiz(TypedDict):
    key: str
    ref: str
    type: Literal["single_choice", "multiple_choice"]
    prompt: str
    options: list[ChoiceOption]


class OrderingQuiz(TypedDict):
    key: str
    ref: str
    type: Literal["ordering"]
    prompt: str
    items: list[ChoiceOption]


class NumericQuiz(TypedDict):
    key: str
    ref: str
    type: Literal["numeric"]
    prompt: str
    unit: NotRequired[str | None]


class ImageFallback(TypedDict):
    type: Literal["image"]
    image_id: str


class TextFallback(TypedDict):
    type: Literal["text"]
    text: str


class ConfigWidget(TypedDict):
    status: Literal["ready"]
    kind: Literal["config"]
    widget_id: str
    title: str
    primitive_id: str
    mode: str
    params: dict[str, JsonValue]


class CodeWidget(TypedDict):
    status: Literal["ready"]
    kind: Literal["code"]
    widget_id: str
    title: str
    labels: NotRequired[dict[str, str]]
    compiled_js: NotRequired[str | None]


class PendingWidget(TypedDict):
    status: Literal["pending", "fallback"]
    title: str
    fallback: ImageFallback | TextFallback


class PartImage(TypedDict):
    image_id: str
    caption: NotRequired[str | None]
    url: NotRequired[str | None]


class SourceSpan(TypedDict):
    start: int
    end: int


class PartSection(TypedDict):
    title: str
    anchor: str
    topic_id: str
    source_span: SourceSpan
    page: NotRequired[int | None]


class PublicPartContent(TypedDict):
    title: str
    markdown: str
    schema_version: NotRequired[Literal[1]]
    key_terms: NotRequired[list[str]]
    widgets: NotRequired[dict[str, ConfigWidget | CodeWidget | PendingWidget]]
    images: NotRequired[dict[str, PartImage]]
    quizzes: NotRequired[list[ChoiceQuiz | OrderingQuiz | NumericQuiz]]
    sources: NotRequired[dict[str, SourceSpan]]
    sections: NotRequired[list[PartSection]]
