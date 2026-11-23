"""Input and output contracts of the solver main pass (story 2.2).

The pass rewrites one part of a document for one reader, places directive
slots for the resolver (2.4) and the quiz generator (2.6), and lists the
key terms for the progress screen (Э5).

The provider-facing answer schema (``PageDraft``) lives in
``services/solver/main_pass/directives.py``: pydantic stays at the model
boundary, while these frozen dataclasses are what the rest of the app
stores and passes around.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from src.app.contracts.documents.topic_node import TopicNode

DirectiveKind = Literal["widget", "image", "quiz"]
DIRECTIVE_KINDS: tuple[DirectiveKind, ...] = ("widget", "image", "quiz")

# A ref carries its kind in the first letter (w1, i1, q1); the schema and
# the parser both enforce it, so the resolver can trust the pair.
REF_PREFIX: dict[DirectiveKind, str] = {"widget": "w", "image": "i", "quiz": "q"}

ReaderLevel = Literal["novice", "intermediate", "advanced"]
ReaderGoal = Literal["exam", "understand", "refresh"]
ReaderDepth = Literal["overview", "standard", "deep"]

_LEVELS = frozenset({"novice", "intermediate", "advanced"})
_GOALS = frozenset({"exam", "understand", "refresh"})
_DEPTHS = frozenset({"overview", "standard", "deep"})


@dataclass(frozen=True, slots=True)
class ReaderProfile:
    """The three answers of the generation wizard (screen Э4)."""

    level: ReaderLevel
    goal: ReaderGoal
    depth: ReaderDepth

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ReaderProfile":
        """Read the profile stored on a part; reject unknown values early."""
        level, goal, depth = raw.get("level"), raw.get("goal"), raw.get("depth")
        for field, value, allowed in (
            ("level", level, _LEVELS),
            ("goal", goal, _GOALS),
            ("depth", depth, _DEPTHS),
        ):
            if value not in allowed:
                raise ValueError(f"Unknown reader profile {field}: {value!r}")
        return cls(
            level=cast(ReaderLevel, level),
            goal=cast(ReaderGoal, goal),
            depth=cast(ReaderDepth, depth),
        )


@dataclass(frozen=True, slots=True)
class PartImage:
    """A picture of the current part as the model sees it.

    ``alias`` is a short synthetic name (``img-1``) shown to the model
    instead of the database id; ``MainPassResult.image_ids`` maps it back
    to ``images.id`` after the call. Caption and description come from the
    uploaded file, so they are data and are escaped before the prompt.
    """

    id: UUID
    alias: str
    caption: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class MainPassDirective:
    """One slot the model asks the resolver or the generator to fill.

    ``ref`` is the identifier written into the markdown
    (``::widget{ref="w1"}``), ``kind`` tells which subsystem owns the slot,
    ``intent`` is the model's brief for it. ``primitive_hint``/``mode_hint``
    are soft suggestions for the resolver; ``image_alias`` names a source
    picture for ``kind="image"``. Refs are unique across kinds: a part's
    widget usages are keyed by ``(part_id, directive_ref)``.
    """

    ref: str
    kind: DirectiveKind
    intent: str
    primitive_hint: str | None = None
    mode_hint: str | None = None
    image_alias: str | None = None


@dataclass(frozen=True, slots=True)
class MainPassInput:
    """Everything the pass sees before the model call.

    ``document_title`` and ``outline`` are document-level on purpose: every
    part of one document must build the same second cached block, so the
    part's own topics are deliberately absent here. ``part_title``,
    ``part_topics``, ``images`` and ``part_markdown`` are volatile and go
    into the user message only.
    """

    document_id: UUID
    part_id: UUID
    document_title: str
    outline: tuple[TopicNode, ...]
    part_title: str
    part_markdown: str
    part_topics: tuple[str, ...]
    profile: ReaderProfile
    images: tuple[PartImage, ...] = ()


@dataclass(frozen=True, slots=True)
class MainPassDraft:
    """Validated page draft: the page and the slots to resolve."""

    markdown: str
    directives: tuple[MainPassDirective, ...]
    key_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DirectiveSpan:
    """Offsets of one directive line in the draft markdown.

    ``start`` is the offset of the first ``:`` and ``end`` is the offset
    just after the closing brace, so the resolver can replace or remove the
    slot without parsing the page again.
    """

    ref: str
    kind: DirectiveKind
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class MainPassResult:
    """What the pipeline stores after a successful pass.

    ``spans`` are the directive offsets in the draft; ``image_ids`` maps
    the aliases used by image directives to real ``images.id`` values.
    """

    draft: MainPassDraft
    spans: tuple[DirectiveSpan, ...]
    image_ids: Mapping[str, UUID]
