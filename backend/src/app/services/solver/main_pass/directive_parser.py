"""Parse and validate the supported remark-directive subset."""

import re
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import cast

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock
from pydantic import ValidationError

from src.app.contracts.solver.main_pass import DirectiveKind
from src.app.services.solver.main_pass.directives import Directive, PageDraft

_DIRECTIVE = re.compile(r'^::(widget|image|quiz)\{(ref|id)="([^"]+)"\}[ \t]*$')
_CANDIDATE = re.compile(r"^[ \t]*(?:>[ \t]*)*(?:(?:[-+*]|\d+[.)])[ \t]+)*:{2,3}(widget|image|quiz)\b")
_INLINE = re.compile(r"(?<![\\:]):(?:widget|image|quiz)(?:\[[^\]\r\n]*\](?:\{[^}\r\n]*\})?|\{[^}\r\n]*\})")
_CODE_SPAN = re.compile(r"(`+)(?!`)(.*?)(?<!`)\1(?!`)")


def _source_lines(markdown: str) -> Iterator[str]:
    """Split only on CommonMark line endings, retaining original characters and offsets."""
    for match in re.finditer(r"[^\r\n]*(?:\r\n|\r|\n|$)", markdown):
        if match.group():
            yield match.group()


def _inline_directives(line: str) -> list[re.Match[str]]:
    masked = _CODE_SPAN.sub(lambda match: " " * len(match.group()), line)
    return list(_INLINE.finditer(masked))


_LEAF_BLOCK = re.compile(r"^::(?:widget|image|quiz)(?:\[[^]\r\n]*\])?(?:\{[^}\r\n]*\})?[ \t]*$")


def _leaf_directive(state: StateBlock, start_line: int, end_line: int, silent: bool) -> bool:
    """Recognize leaf blocks before CommonMark decides where code starts."""
    if state.is_code_block(start_line):
        return False
    start = state.bMarks[start_line] + state.tShift[start_line]
    if not _LEAF_BLOCK.fullmatch(state.src[start : state.eMarks[start_line]]):
        return False
    if silent:
        return True
    state.line = start_line + 1
    token = state.push("solver_directive", "", 0)
    token.map = [start_line, state.line]
    return True


def _block_lines(markdown: str) -> tuple[set[int], set[int]]:
    """Find code and directive blocks with list and blockquote context."""
    parser = MarkdownIt("commonmark")
    parser.block.ruler.before("paragraph", "solver_directive", _leaf_directive, {"alt": ["paragraph"]})
    code: set[int] = set()
    directives: set[int] = set()
    for token in parser.parse(markdown):
        if token.map is None:
            continue
        if token.type in {"fence", "code_block"}:
            code.update(range(token.map[0] + 1, token.map[1] + 1))
        elif token.type == "solver_directive":
            directives.add(token.map[0] + 1)
    return code, directives


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
    offset = 0
    code_lines, block_directives = _block_lines(markdown)
    for number, raw in enumerate(_source_lines(markdown), 1):
        line = raw.rstrip("\r\n")
        start = offset
        offset += len(raw)
        if number in code_lines:
            continue
        if _inline_directives(line):
            issues.append(f"line {number}: inline directives are not supported")
        if number not in block_directives and not _CANDIDATE.match(line):
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
            elif draft.markdown[end : end + 1] in {"\r", "\n"}:
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
    code_lines, block_directives = _block_lines(draft.markdown)
    marker_lines = {m.line for m in markers}
    for number, raw in enumerate(_source_lines(draft.markdown), 1):
        line = raw.rstrip("\r\n")
        if number not in code_lines and number not in marker_lines:
            if number in block_directives or _CANDIDATE.match(line):
                removed.append((offset, offset + len(raw)))
            else:
                removed.extend((offset + item.start(), offset + item.end()) for item in _inline_directives(line))
        offset += len(raw)
    markdown = draft.markdown
    for start, end in sorted(removed, reverse=True):
        # Remove the colons of a newly exposed marker; keep whitespace and surrounding text.
        removed_text = markdown[start:end]
        following = (
            re.match(r"([ \t]*)::", markdown[end:]) if "\n" not in removed_text and "\r" not in removed_text else None
        )
        replacement = ""
        if following:
            whitespace = following.group(1)
            end += len(whitespace) + 2
            replacement = whitespace
        markdown = markdown[:start] + replacement + markdown[end:]
    try:
        return PageDraft.model_validate(
            {
                "markdown": markdown,
                "directives": kept,
                "key_terms": [term for term in draft.key_terms if term in markdown],
            }
        )
    except ValidationError as exc:
        raise UnrecoverableDraftError("Sanitization cannot preserve the output schema") from exc


class UnrecoverableDraftError(ValueError):
    """The draft cannot be repaired without inventing content."""
