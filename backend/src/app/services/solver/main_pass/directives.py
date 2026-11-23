"""Provider-facing answer schema of the main pass (story 2.2).

``PageDraft`` is the pydantic schema handed to ``call_structured``. Both
models forbid unknown fields: a provider that invents an attribute must be
retried, not silently accepted. Field descriptions double as the JSON
schema documentation sent to the model.

The model validator enforces the structural contract (refs match kinds,
markdown and list agree one-to-one). Semantic rules that need part context
(image aliases, widget limit, alternation) are checked by the service after
the call. ``to_draft`` converts the wire model to immutable contracts.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.app.contracts.solver.main_pass import (
    REF_PREFIX,
    DirectiveKind,
    MainPassDirective,
    MainPassDraft,
)
from src.app.services.solver.main_pass.directive_parser import check_draft

_Ref = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=16, pattern=r"^[a-z][a-z0-9]*$"),
]
_Intent = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
_Hint = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
_Alias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9-]*$"),
]
_KeyTerm = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Directive(BaseModel):
    """One slot for the resolver (2.4) or the quiz generator (2.6)."""

    model_config = ConfigDict(extra="forbid")

    ref: _Ref = Field(
        description=(
            'Reference written into the markdown. The first letter encodes the kind: '
            '"w1" for widget, "i1" for image, "q1" for quiz.'
        )
    )
    kind: DirectiveKind = Field(
        description=(
            '"widget" for an interactive visualization, "image" for a figure '
            'taken from the source document, "quiz" for a check of understanding.'
        )
    )
    intent: _Intent = Field(
        description="What the element must show, explain or ask; the resolver picks the primitive from it."
    )
    primitive_hint: _Hint | None = Field(
        default=None,
        description='Optional catalog primitive id for a widget, e.g. "three-frame"; the resolver may override it.',
    )
    mode_hint: _Hint | None = Field(
        default=None,
        description='Optional catalog mode for a widget, e.g. "steps"; the resolver may override it.',
    )
    image_alias: _Alias | None = Field(
        default=None,
        description='For kind="image": the alias of a source picture from the <images> block, e.g. "img-1".',
    )

    @model_validator(mode="after")
    def _fields_match_kind(self) -> Self:
        prefix = REF_PREFIX[self.kind]
        if not self.ref.startswith(prefix):
            raise ValueError(f"ref {self.ref!r} must start with {prefix!r} for kind {self.kind!r}")
        if self.kind == "image":
            if self.image_alias is None:
                raise ValueError('kind "image" requires image_alias')
            if self.primitive_hint is not None or self.mode_hint is not None:
                raise ValueError("image directives cannot carry primitive_hint or mode_hint")
        else:
            if self.image_alias is not None:
                raise ValueError(f'image_alias is only allowed for kind "image", not {self.kind!r}')
            if self.kind != "widget" and (self.primitive_hint is not None or self.mode_hint is not None):
                raise ValueError("primitive_hint and mode_hint are only allowed for kind \"widget\"")
        return self


class PageDraft(BaseModel):
    """Rewritten part plus its slots and key terms; validated as a whole."""

    model_config = ConfigDict(extra="forbid")

    markdown: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="The rewritten part in Markdown with every directive on its own line."
    )
    directives: list[Directive] = Field(
        default_factory=list,
        description="One entry per directive in the markdown: same ref, same kind, unique refs.",
    )
    key_terms: list[_KeyTerm] = Field(
        min_length=1,
        max_length=30,
        description="Terms a reader must remember, taken from the source part, in the source language.",
    )

    @model_validator(mode="after")
    def _directives_match_markdown(self) -> Self:
        violations = check_draft(self.markdown, self.directives)
        if violations:
            raise ValueError("; ".join(violations))
        return self

    def to_draft(self) -> MainPassDraft:
        """Convert the wire answer to the immutable contracts of the pass."""
        return MainPassDraft(
            markdown=self.markdown,
            directives=tuple(
                MainPassDirective(
                    ref=directive.ref,
                    kind=directive.kind,
                    intent=directive.intent,
                    primitive_hint=directive.primitive_hint,
                    mode_hint=directive.mode_hint,
                    image_alias=directive.image_alias,
                )
                for directive in self.directives
            ),
            key_terms=tuple(self.key_terms),
        )


__all__ = ["Directive", "PageDraft"]
