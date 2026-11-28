"""Structured output schemas for resolver LLM calls (story 2.4)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CandidateLabel = Literal["c1", "c2", "c3", "c4", "c5"]


class RerankVerdict(BaseModel):
    """Reranker's choice among candidates (story 2.4.1)."""

    model_config = ConfigDict(extra="forbid")

    choice: CandidateLabel | None = Field(
        description="Best candidate label, or null if none fits."
    )
    fits_as_is: bool = Field(
        description="True if the candidate already shows the data from the fragment."
    )
    reason: str = Field(max_length=300)


class ConfigDraft(BaseModel):
    """Proposed widget configuration from the main model (story 2.4.3)."""

    model_config = ConfigDict(extra="forbid")

    primitive_id: str | None = Field(
        description="Primitive id from the catalog, or null if no primitive fits."
    )
    mode: str | None = None
    params_json: str = Field(description="Params as a JSON object that matches the primitive params schema.")
    reason: str = Field(max_length=300)


class IntentCheck(BaseModel):
    """Cheap model's check of config vs intent (story 2.4.4)."""

    model_config = ConfigDict(extra="forbid")

    matches: bool
    issues: list[str] = Field(default_factory=list, max_length=5)


class WidgetDescriptionDraft(BaseModel):
    """Description and paraphrases for a new widget (story 2.4.6)."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=40, max_length=500)
    paraphrases: list[str] = Field(min_length=3, max_length=5)


__all__ = [
    "CandidateLabel",
    "ConfigDraft",
    "IntentCheck",
    "RerankVerdict",
    "WidgetDescriptionDraft",
]