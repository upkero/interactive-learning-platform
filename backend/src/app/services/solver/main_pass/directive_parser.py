"""Parse and validate the supported remark-directive subset."""

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import cast

from src.app.contracts.solver.main_pass import DirectiveKind
from src.app.services.solver.main_pass.directives import Directive, PageDraft

_FENCE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_DIRECTIVE = re.compile(r'^::(widget|image|quiz)\{(ref|id)="([^"]+)"\}\s*$')
_CANDIDATE = re.compile(r"^\s*(?:>\s*)*(?:(?:[-+*]|\d+[.)])\s+)?:{2,3}(widget|image|quiz)\b")
_INLINE = re.compile(r"(?<![\\:]):(?:widget|image|quiz)\[[^\]\r\n]*(?:\](?:\{[^}\r\n]*\})?|$)")
_CODE_SPAN = re.compile(r"(`+)(?!`)(.*?)(?<!`)\1(?!`)")
_BLOCKQUOTE = re.compile(r"^ {0,3}(?:> ?)+")


def _inline_directives(line: str) -> list[re.Match[str]]:
    masked = _CODE_SPAN.sub(lambda match: " " * len(match.group()), line)
    return list(_INLINE.finditer(masked))


def _fence_match(line: str) -> tuple[re.Match[str] | None, int]:
    quote = _BLOCKQUOTE.match(line)
    depth = quote.group().count(">") if quote else 0
    return _FENCE.match(line[quote.end() :] if quote else line), depth


@dataclass(frozen=True, slots=True)
class Marker:
    ref: str
    kind: DirectiveKind
    start: int
    end: int
    line: int


def extract_markers(markdown: str) -> tuple[list[Marker], list[str]]:
    markers: list[Marker] = []
    issues: list[str] = []
    fence: tuple[str, int, int] | None = None
    offset = 0
    for number, raw in enumerate(markdown.splitlines(keepends=True), 1):
        line = raw.rstrip("\r\n")
        start = offset
        offset += len(raw)
        match, depth = _fence_match(line)
        if fence and depth < fence[2]:
            fence = None
        if fence:
            if (
                depth == fence[2]
                and match
                and match["fence"][0] == fence[0]
                and len(match["fence"]) >= fence[1]
                and not match["info"].strip()
            ):
                fence = None
            continue
        if match:
            fence = (match["fence"][0], len(match["fence"]), depth)
            continue
        if _inline_directives(line):
            issues.append(f"line {number}: inline directives are not supported")
        if not _CANDIDATE.match(line):
            continue
        match = _DIRECTIVE.fullmatch(line)
        if not match or (match[1] == "image") != (match[2] == "id"):
            issues.append(f"line {number}: directive must be an unindented leaf with only ref or image id")
            continue
        markers.append(Marker(match[3], cast(DirectiveKind, match[1]), start, start + len(line), number))
    return markers, issues


def check_draft(
    markdown: str,
    directives: Sequence[Directive],
    *,
    image_aliases: Collection[str] | None = None,
    max_widgets: int | None = None,
    max_quizzes: int | None = None,
    alternation: bool = False,
    key_terms: Sequence[str] | None = None,
) -> list[str]:
    markers, issues = extract_markers(markdown)
    declared: dict[str, Directive] = {}
    for entry in directives:
        if entry.ref in declared:
            issues.append(f"duplicate directive ref {entry.ref!r} in the directive list")
        else:
            declared[entry.ref] = entry
    seen: set[str] = set()
    images: set[str] = set()
    for marker in markers:
        if marker.ref in seen:
            issues.append(f"directive ref {marker.ref!r} appears more than once in the markdown")
        seen.add(marker.ref)
        target = declared.get(marker.ref)
        if target is None:
            issues.append(f"markdown directive {marker.ref!r} has no entry in the directive list")
        elif target.kind != marker.kind:
            issues.append(f"directive {marker.ref!r} has different kinds in markdown and list")
        if marker.kind == "image":
            if image_aliases is not None and marker.ref not in image_aliases:
                issues.append(f"unknown image id {marker.ref!r}")
            if marker.ref in images:
                issues.append(f"image id {marker.ref!r} is used more than once")
            images.add(marker.ref)
    for ref in declared.keys() - seen:
        issues.append(f"directive {ref!r} missing from the markdown")
    for kind, limit in (("widget", max_widgets), ("quiz", max_quizzes)):
        count = sum(m.kind == kind for m in markers)
        if limit is not None and count > limit:
            issues.append(f"too many {kind} directives: {count} > {limit}")
    if alternation:
        widgets = [
            declared[m.ref]
            for m in markers
            if m.kind == "widget" and m.ref in declared and declared[m.ref].kind == "widget"
        ]
        for previous, current in pairwise(widgets):
            if (
                previous.primitive_hint is not None
                and previous.mode_hint is not None
                and (previous.primitive_hint, previous.mode_hint) == (current.primitive_hint, current.mode_hint)
            ):
                issues.append(f"widgets {previous.ref!r} and {current.ref!r} have identical primitive and mode")
    if key_terms is not None:
        for term in key_terms:
            if term not in markdown:
                issues.append(f"key term {term!r} is absent from markdown")
    return issues


def sanitize_draft(
    draft: PageDraft, *, max_widgets: int, max_quizzes: int = 5, image_aliases: Collection[str] | None = None
) -> PageDraft:
    markers, _ = extract_markers(draft.markdown)
    entries: dict[str, Directive] = {}
    for directive in draft.directives:
        entries.setdefault(directive.ref, directive)
    kept: list[Directive] = []
    removed: list[tuple[int, int]] = []
    used: set[str] = set()
    counts = {"widget": 0, "quiz": 0}
    previous_widget: Directive | None = None
    for marker in markers:
        entry = entries.get(marker.ref)
        valid = entry is not None and entry.kind == marker.kind and marker.ref not in used
        if marker.kind == "image" and image_aliases is not None and marker.ref not in image_aliases:
            valid = False
        if marker.kind in counts:
            limit = max_widgets if marker.kind == "widget" else max_quizzes
            if counts[marker.kind] >= limit:
                valid = False
        if not valid or entry is None:
            end = marker.end
            if draft.markdown[end : end + 2] == "\r\n":
                end += 2
            elif draft.markdown[end : end + 1] == "\n":
                end += 1
            removed.append((marker.start, end))
            continue
        used.add(marker.ref)
        if marker.kind in counts:
            counts[marker.kind] += 1
        if marker.kind == "widget":
            if (
                previous_widget
                and previous_widget.primitive_hint is not None
                and previous_widget.mode_hint is not None
                and (previous_widget.primitive_hint, previous_widget.mode_hint)
                == (entry.primitive_hint, entry.mode_hint)
            ):
                entry = entry.model_copy(update={"mode_hint": None})
            previous_widget = entry
        kept.append(entry)
    # Remove malformed directive lines too, so the frontend cannot render unknown slots.
    offset = 0
    marker_lines = {m.line for m in markers}
    fence: tuple[str, int, int] | None = None
    for number, raw in enumerate(draft.markdown.splitlines(keepends=True), 1):
        line = raw.rstrip("\r\n")
        match, depth = _fence_match(line)
        if fence and depth < fence[2]:
            fence = None
        if fence:
            if (
                depth == fence[2]
                and match
                and match["fence"][0] == fence[0]
                and len(match["fence"]) >= fence[1]
                and not match["info"].strip()
            ):
                fence = None
        elif match:
            fence = (match["fence"][0], len(match["fence"]), depth)
        elif number not in marker_lines and _CANDIDATE.match(line):
            removed.append((offset, offset + len(raw)))
        elif number not in marker_lines:
            removed.extend((offset + item.start(), offset + item.end()) for item in _inline_directives(line))
        offset += len(raw)
    markdown = draft.markdown
    for start, end in sorted(removed, reverse=True):
        markdown = markdown[:start] + markdown[end:]
    return draft.model_copy(
        update={
            "markdown": markdown,
            "directives": kept,
            "key_terms": [term for term in draft.key_terms if term in markdown],
        }
    )
