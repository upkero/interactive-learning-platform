"""Parse and check the remark-directive slots of a main-pass draft.

A slot is a leaf directive that occupies a whole line::

    ::widget{ref="w1"}

The parser reads ``ref`` and the optional ``primitive_hint``,
``mode_hint`` and ``image_alias`` attributes; unknown extra attributes are
kept in ``Marker.attrs`` and ignored. Lines inside fenced code blocks are
not slots. The syntax is the same subset that remark-directive understands
on the frontend (screen Э6), so the shared examples live in
``tests/support/fixtures/main_pass/directives.md``.

``check_draft`` proves that the markdown and the directive list describe
exactly the same slots (one occurrence each, same kind), checks source
image aliases, the widget limit and the alternation rule. ``PageDraft``
runs the structural part as a model validator, so a contradiction is a
schema error and ``call_structured`` retries once with the broken reply;
the service runs the semantic part and sanitises what survived the retry.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING, Protocol, cast

from src.app.contracts.solver.main_pass import (
    DIRECTIVE_KINDS,
    DirectiveKind,
    DirectiveSpan,
)

if TYPE_CHECKING:
    from src.app.services.solver.main_pass.directives import PageDraft

_DIRECTIVE = re.compile(r"^::(?P<kind>[a-z][a-z0-9-]*)\{(?P<attrs>[^}\n]*)\}\s*$")
_ATTR = re.compile(
    r"""(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s*=\s*"""
    r"""(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^\s}"']+))"""
)
_FENCE = re.compile(r"^(?:```|~~~)")


class DirectiveError(ValueError):
    """The markdown syntax is malformed or disagrees with the directive list."""


class DirectiveLike(Protocol):
    """Read-only view of a declared directive (pydantic ``Directive``)."""

    @property
    def ref(self) -> str: ...

    @property
    def kind(self) -> str: ...

    @property
    def primitive_hint(self) -> str | None: ...

    @property
    def mode_hint(self) -> str | None: ...

    @property
    def image_alias(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class Marker:
    """A slot found in the markdown.

    ``start``/``end`` are offsets of the directive line without the line
    break; ``line`` is 1-based for error messages.
    """

    ref: str
    kind: DirectiveKind
    attrs: dict[str, str]
    start: int
    end: int
    line: int


def extract_markers(markdown: str) -> tuple[Marker, ...]:
    """Return the leaf directives of ``markdown`` in document order."""
    markers: list[Marker] = []
    in_fence = False
    offset = 0
    for number, raw in enumerate(markdown.splitlines(keepends=True), start=1):
        content = raw.rstrip("\r\n")
        start = offset
        offset += len(raw)
        if _FENCE.match(content):
            in_fence = not in_fence
            continue
        if in_fence or not content.startswith("::"):
            continue
        match = _DIRECTIVE.match(content)
        if match is None:
            raise DirectiveError(
                f'line {number}: a directive must be a leaf block like ::widget{{ref="w1"}}'
            )
        kind = match["kind"]
        if kind not in DIRECTIVE_KINDS:
            raise DirectiveError(f"line {number}: unknown directive kind {kind!r}")
        attrs = {
            attr["name"]: attr["double"] or attr["single"] or attr["bare"]
            for attr in _ATTR.finditer(match["attrs"])
        }
        ref = attrs.get("ref", "")
        if not ref:
            raise DirectiveError(f"line {number}: the {kind} directive has no ref attribute")
        markers.append(
            Marker(
                ref=ref,
                kind=cast(DirectiveKind, kind),
                attrs=attrs,
                start=start,
                end=start + len(content),
                line=number,
            )
        )
    return tuple(markers)


def locate_spans(markdown: str) -> tuple[DirectiveSpan, ...]:
    """Offsets of every directive line; used to replace slots without reparsing."""
    spans: list[DirectiveSpan] = []
    seen: set[str] = set()
    for marker in extract_markers(markdown):
        if marker.ref in seen:
            raise DirectiveError(f"directive ref {marker.ref!r} appears more than once in the markdown")
        seen.add(marker.ref)
        spans.append(
            DirectiveSpan(ref=marker.ref, kind=marker.kind, start=marker.start, end=marker.end)
        )
    return tuple(spans)


def check_draft(
    markdown: str,
    directives: Sequence[DirectiveLike],
    *,
    image_aliases: Collection[str] | None = None,
    max_widgets: int | None = None,
    alternation: bool = False,
) -> list[str]:
    """Return human-readable violations; an empty list means the draft is good.

    The optional checks are the ones that need data from outside the model
    answer: ``image_aliases`` (source pictures available to the part),
    ``max_widgets`` (part limit) and ``alternation`` (two widgets in a row
    must differ in primitive or mode). ``PageDraft`` runs only the
    structural part; the service adds the rest.
    """
    try:
        markers = extract_markers(markdown)
    except DirectiveError as exc:
        return [str(exc)]

    violations: list[str] = []
    declared: dict[str, DirectiveLike] = {}
    for directive in directives:
        if directive.ref in declared:
            violations.append(f"duplicate directive ref {directive.ref!r} in the directive list")
            continue
        declared[directive.ref] = directive

    seen: set[str] = set()
    for marker in markers:
        if marker.ref in seen:
            violations.append(f"directive ref {marker.ref!r} appears more than once in the markdown")
            continue
        seen.add(marker.ref)
        target = declared.get(marker.ref)
        if target is None:
            violations.append(f"markdown directive {marker.ref!r} has no entry in the directive list")
            continue
        if target.kind != marker.kind:
            violations.append(
                f"directive {marker.ref!r} is {marker.kind!r} in the markdown but {target.kind!r} in the list"
            )

    missing = sorted(set(declared) - seen)
    if missing:
        violations.append(f"directives missing from the markdown: {', '.join(missing)}")

    if image_aliases is not None:
        violations.extend(_check_images(markers, declared, image_aliases))

    if max_widgets is not None:
        widgets = [marker for marker in markers if marker.kind == "widget"]
        if len(widgets) > max_widgets:
            refs = ", ".join(marker.ref for marker in widgets[max_widgets:])
            violations.append(f"too many widgets: {len(widgets)} > {max_widgets} (extra: {refs})")

    if alternation:
        violations.extend(_check_alternation(markdown, markers, declared))

    return violations


def sanitize_draft(
    draft: PageDraft,
    *,
    max_widgets: int,
    image_aliases: Collection[str] | None = None,
) -> PageDraft:
    """Repair what survived the retry, without inventing content.

    - image directives with an unknown or already used alias are removed
      (the resolver cannot place them);
    - widgets beyond ``max_widgets`` are removed;
    - when two widgets still follow each other with the same primitive and
      mode, the second loses ``mode_hint`` and the resolver picks a mode.
    The function is idempotent: sanitising a sanitised draft changes nothing.
    """
    payload = draft.model_dump()
    markdown: str = payload["markdown"]
    entries: list[dict[str, object]] = payload["directives"]
    markers = list(extract_markers(markdown))

    by_ref = {str(entry["ref"]): entry for entry in entries}
    dropped: list[Marker] = []
    if image_aliases is not None:
        used_aliases: set[str] = set()
        for marker in markers:
            if marker.kind != "image":
                continue
            alias = by_ref[marker.ref].get("image_alias")
            if alias not in image_aliases or alias in used_aliases:
                dropped.append(marker)
            else:
                used_aliases.add(str(alias))

    widgets = [marker for marker in markers if marker.kind == "widget" and marker not in dropped]
    dropped.extend(widgets[max_widgets:])
    if dropped:
        dropped_refs = {marker.ref for marker in dropped}
        markdown = _without_lines(markdown, [(marker.start, marker.end) for marker in dropped])
        entries = [entry for entry in entries if entry["ref"] not in dropped_refs]

    # Offsets changed if lines were removed, so locate the slots again.
    markers = list(extract_markers(markdown))
    mode_resets: list[Marker] = []
    for previous, current in pairwise(markers):
        if previous.kind != "widget" or current.kind != "widget":
            continue
        if markdown[previous.end : current.start].strip():
            continue
        earlier, later = by_ref[previous.ref], by_ref[current.ref]
        same_primitive = earlier.get("primitive_hint") == later.get("primitive_hint")
        same_mode = earlier.get("mode_hint") == later.get("mode_hint")
        if same_primitive and same_mode and later.get("mode_hint") is not None:
            later["mode_hint"] = None
            mode_resets.append(current)

    if mode_resets:
        markdown = _without_attributes(markdown, mode_resets, names=("mode_hint",))

    if not dropped and not mode_resets:
        return draft
    return type(draft).model_validate({**payload, "markdown": markdown, "directives": entries})


def _check_images(
    markers: Sequence[Marker],
    declared: dict[str, DirectiveLike],
    image_aliases: Collection[str],
) -> list[str]:
    violations: list[str] = []
    used: set[str] = set()
    for marker in markers:
        if marker.kind != "image" or marker.ref not in declared:
            continue
        alias = declared[marker.ref].image_alias
        if alias is None:
            violations.append(f"image directive {marker.ref!r} has no image_alias")
        elif alias not in image_aliases:
            violations.append(f"image directive {marker.ref!r} uses unknown image alias {alias!r}")
        elif alias in used:
            violations.append(f"image alias {alias!r} is used more than once")
        else:
            used.add(alias)
    return violations


def _check_alternation(
    markdown: str,
    markers: Sequence[Marker],
    declared: dict[str, DirectiveLike],
) -> list[str]:
    violations: list[str] = []
    widgets = [marker for marker in markers if marker.kind == "widget" and marker.ref in declared]
    for previous, current in pairwise(widgets):
        if markdown[previous.end : current.start].strip():
            continue
        earlier, later = declared[previous.ref], declared[current.ref]
        if earlier.primitive_hint != later.primitive_hint or earlier.mode_hint != later.mode_hint:
            continue
        if later.mode_hint is None:
            continue
        violations.append(
            f"widgets {previous.ref!r} and {current.ref!r} follow each other with primitive "
            f"{later.primitive_hint!r} and mode {later.mode_hint!r}; change the mode, use another "
            "primitive, or merge them into one widget"
        )
    return violations


def _without_lines(markdown: str, spans: Sequence[tuple[int, int]]) -> str:
    result = markdown
    for start, end in sorted(spans, reverse=True):
        if result.startswith("\r\n", end):
            end += 2
        elif result.startswith("\n", end):
            end += 1
        result = result[:start] + result[end:]
    return result


def _without_attributes(markdown: str, markers: Sequence[Marker], *, names: Sequence[str]) -> str:
    """Remove the given attributes from the directive lines, keeping the refs."""
    result = markdown
    patterns = [
        re.compile(r"\s+" + re.escape(name) + r"\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s}]+)")
        for name in names
    ]
    for marker in sorted(markers, key=lambda item: item.start, reverse=True):
        line = result[marker.start : marker.end]
        for pattern in patterns:
            line = pattern.sub("", line)
        result = result[: marker.start] + line + result[marker.end :]
    return result


__all__ = [
    "DirectiveError",
    "DirectiveLike",
    "Marker",
    "check_draft",
    "extract_markers",
    "locate_spans",
    "sanitize_draft",
]
