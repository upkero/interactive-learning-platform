"""Provider-facing structured answer for the solver main pass."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.app.contracts.solver.main_pass import (
    REF_PREFIX,
    DirectiveKind,
    MainPassDirective,
    MainPassDraft,
    PrimitiveMode,
)
from src.app.core.settings.solver import MAX_KEY_TERMS, MIN_KEY_TERMS

_Ref = Annotated[str, StringConstraints(pattern=r"^(w[1-9][0-9]?|q[1-9][0-9]?|img_[1-9][0-9]?)$")]
_KeyTerm = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Directive(BaseModel):
    """A slot and a verbatim source quotation for the resolver or quiz generator."""

    model_config = ConfigDict(extra="forbid")

    ref: _Ref
    kind: DirectiveKind
    intent: str = Field(min_length=10, max_length=400, description="What the learner sees or is asked.")
    primitive_hint: str | None = Field(default=None, description="Primitive id from the catalog or null.")
    mode_hint: PrimitiveMode | None = None
    params_hint: str | None = Field(default=None, max_length=600, description="Concrete data from the source.")
    image_id: str | None = Field(default=None, pattern=r"^img_[1-9][0-9]?$")
    source_span: str = Field(min_length=10, max_length=300, description="Verbatim quote from the source document.")

    @model_validator(mode="after")
    def _fields_match_kind(self) -> Self:
        if not self.ref.startswith(REF_PREFIX[self.kind]):
            raise ValueError(f"ref {self.ref!r} does not match kind {self.kind!r}")
        if self.kind == "image":
            if self.image_id != self.ref:
                raise ValueError("image directive: image_id must equal ref")
            if self.params_hint is not None:
                raise ValueError("image directive has no params_hint")
        elif self.image_id is not None:
            raise ValueError("image_id is only allowed for image directives")
        if self.kind != "widget" and (self.primitive_hint is not None or self.mode_hint is not None):
            raise ValueError("primitive and mode hints are only allowed for widget directives")
        return self


class RecoveredPageDraft(BaseModel):
    """Final draft after invalid slots and key terms have been removed."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, description="The rewritten part in Markdown.")
    directives: list[Directive] = Field(default_factory=list, max_length=24)
    key_terms: list[_KeyTerm] = Field(max_length=MAX_KEY_TERMS, description="Terms appearing verbatim in Markdown.")

    @model_validator(mode="after")
    def _has_content(self) -> Self:
        if not self.markdown.strip():
            raise ValueError("The page must contain Markdown content")
        return self

    def to_draft(self) -> MainPassDraft:
        return MainPassDraft(
            markdown=self.markdown,
            directives=tuple(MainPassDirective(**directive.model_dump()) for directive in self.directives),
            key_terms=tuple(self.key_terms),
        )


class PageDraft(RecoveredPageDraft):
    """Model response with the length and terminology targets for generation."""

    markdown: str = Field(min_length=200, description="The rewritten part in Markdown.")
    key_terms: list[_KeyTerm] = Field(
        min_length=MIN_KEY_TERMS, max_length=MAX_KEY_TERMS, description="Terms appearing verbatim in Markdown."
    )


__all__ = ["Directive", "PageDraft", "RecoveredPageDraft"]
