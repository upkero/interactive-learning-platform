"""Parse and validate the supported remark-directive subset."""

import re
from bisect import bisect_right
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from typing import cast

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock
from markdown_it.rules_inline import StateInline, backtick
from markdown_it.token import Token
from pydantic import ValidationError

from src.app.contracts.solver.main_pass import DirectiveKind
from src.app.services.solver.main_pass.directives import Directive, RecoveredPageDraft

_DIRECTIVE = re.compile(r'^::(widget|image|quiz)\{(ref|id)="([^"]+)"\}[ \t]*$')
_CANDIDATE = re.compile(r"^[ \t]*(?:(?:>[ \t]*|(?:[-+*]|[0-9]{1,9}[.)])[ \t]+))*(:{2,}(?:widget|image|quiz)\b)")
_INLINE_NAME = re.compile(r":(?:widget|image|quiz)(?![\w:-])")
_INLINE_PREFIX = re.compile(r"(?<![\\:]):[a-z]{0,6}\Z")
_ATTRIBUTE_VALUE = r"""(?:"[^"]*"|'[^']*'|[^ \t\n"'<>={`}}]+)"""
_ATTRIBUTES = re.compile(
    r"\{(?>[ \t\n]*(?:[.#][^ \t\n.#\"'<>={`}}]+"
    rf"|[\w:-][\w.:-]*(?:[ \t\n]*=[ \t\n]*{_ATTRIBUTE_VALUE})?))*[ \t\n]*\}}"
)
_BLOCK = re.compile(
    r"(:{2,})([^\W_](?:[\w-]*[^\W_])?)"
    r"(?:\[(?:\\.|[^\\\[\]]|\[[^]]*\])*\])?"
    r"""(?:\{(?:[^{}"'\\]|\\.|"[^"]*"|'[^']*')*\})?[ \t]*"""
)
_CLOSE = re.compile(r"(:{3,})[ \t]*")


def _source_lines(markdown: str) -> Iterator[str]:
    """Split only on CommonMark line endings, retaining original characters and offsets."""
    for match in re.finditer(r"[^\r\n]*(?:\r\n|\r|\n|$)", markdown):
        if match.group():
            yield match.group()


def _directive_block(state: StateBlock, start_line: int, end_line: int, silent: bool) -> bool:
    """Recognize directive boundaries before CommonMark decides where code starts."""
    if state.is_code_block(start_line):
        return False
    start = state.bMarks[start_line] + state.tShift[start_line]
    end = state.eMarks[start_line]
    text = state.src[start:end]
    match = _BLOCK.fullmatch(text) or _CLOSE.fullmatch(text)
    if not match:
        return False
    width = len(match[1])
    if width >= 3:
        # Each list item or quote has its own directive fences.
        parent = (
            next(
                (token for token in reversed(state.tokens) if token.nesting == 1 and token.level == state.level - 1),
                None,
            )
            if state.level
            else None
        )
        containers: dict[int, list[int]] = state.env.setdefault("solver_containers", {})
        widths = containers.get(id(parent), [])
        if match.lastindex == 1:
            closing = next((i for i, opening_width in enumerate(widths) if opening_width <= width), None)
            if closing is None:
                return False
            if not silent:
                del widths[closing:]
        elif not silent:
            containers.setdefault(id(parent), []).append(width)
    if silent:
        return True
    state.line = start_line + 1
    token = state.push("solver_directive", "", 0)
    token.map = [start_line, state.line]
    token.content = text
    return True


def _backtick_with_offsets(state: StateInline, silent: bool) -> bool:
    start, token_count = state.pos, len(state.tokens)
    matched = backtick(state, silent)
    if matched and len(state.tokens) > token_count and state.tokens[-1].type == "code_inline":
        state.tokens[-1].meta["source_span"] = (start, state.pos)
    return matched


def _label_end(source: str, start: int) -> int:
    depth = 1
    pos = start + 1
    while pos < len(source):
        char = source[pos]
        if char == "\\" and source[pos + 1 : pos + 2] in {"\\", "[", "]"}:
            pos += 2
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return pos + 1
        pos += 1
    return start


def _inline_directive(state: StateInline, silent: bool) -> bool:
    start = state.pos
    match = _INLINE_NAME.match(state.src, start, state.posMax)
    if not match:
        return False
    if start and state.src[start - 1] == ":":
        escape = start - 2
        while escape >= 0 and state.src[escape] == "\\":
            escape -= 1
        if (start - 2 - escape) % 2 == 0:
            return False
    source = state.src[: state.posMax]
    end = match.end()
    if source[end : end + 1] == "[":
        end = _label_end(source, end)
    attributes = _ATTRIBUTES.match(source, end)
    if attributes:
        end = attributes.end()
    if not silent:
        token = state.push("solver_inline_directive", "", 0)
        token.meta["source_span"] = (start, end)
    state.pos = end
    return True


def _inline_removals(token: Token, lines: list[str], offsets: list[int]) -> list[tuple[int, int, int]]:
    """Map directive spans from the inline buffer to the original Markdown."""
    if not token.map or not token.children:
        return []
    spans = [child.meta["source_span"] for child in token.children if child.type == "solver_inline_directive"]
    if not spans:
        return []
    positions: list[tuple[int, int, int]] = []
    cursor = 0
    for number, content in enumerate(token.content.split("\n"), token.map[0]):
        # Leading indentation may include spaces synthesized from tabs.
        plain = content.lstrip(" ")
        column = lines[number].replace("\x00", "\ufffd").rfind(plain)
        if column >= 0:
            positions.append((cursor + len(content) - len(plain), offsets[number] + column, number))
        cursor += len(content) + 1
    result: list[tuple[int, int, int]] = []
    for start, end in spans:
        first = bisect_right(positions, start, key=lambda point: point[0]) - 1
        last = bisect_right(positions, end - 1, key=lambda point: point[0]) - 1
        inline_start, original_start, number = positions[first]
        inline_end, original_end, _ = positions[last]
        result.append((original_start + start - inline_start, original_end + end - inline_end, number))
    return result


def _mask_inline_code(token: Token, lines: list[str], masked: list[str]) -> None:
    """Map CommonMark code spans back to source lines, including container prefixes."""
    if not token.map or not token.children:
        return
    content = token.content
    spans = [child.meta["source_span"] for child in token.children if child.type == "code_inline"]
    if not spans:
        return
    pieces: list[str] = []
    end = 0
    for start, stop in spans:
        pieces.append(content[end:start])
        pieces.append(re.sub(r"[^\n]", " ", content[start:stop]))
        end = stop
    pieces.append(content[end:])
    for i, (plain, hidden) in enumerate(zip(content.split("\n"), "".join(pieces).split("\n"), strict=True)):
        if plain == hidden:
            continue
        number = token.map[0] + i
        # Block parsing strips quote/list prefixes and can synthesize spaces from tabs.
        plain = plain.lstrip(" ")
        hidden = hidden[-len(plain) :] if plain else ""
        start = lines[number].replace("\x00", "\ufffd").rfind(plain)
        if start >= 0 and hidden:
            masked[number] = lines[number][:start] + hidden + lines[number][start + len(plain) :]


def _markdown_context(
    markdown: str, lines: list[str], offsets: list[int]
) -> tuple[set[int], dict[int, int], list[str], list[tuple[int, int, int]]]:
    parser = MarkdownIt("commonmark")
    parser.block.ruler.before("paragraph", "solver_directive", _directive_block, {"alt": ["paragraph"]})
    parser.inline.ruler.at("backticks", _backtick_with_offsets)
    parser.inline.add_terminator_char(":")
    parser.inline.ruler.before("text", "solver_inline_directive", _inline_directive)
    code: set[int] = set()
    directives: dict[int, int] = {}
    masked = lines.copy()
    inline_removals: list[tuple[int, int, int]] = []
    for token in parser.parse(markdown):
        if token.map is None:
            continue
        number = token.map[0]
        if token.type in {"fence", "code_block"}:
            code.update(range(number, token.map[1]))
        elif token.type == "solver_directive":
            directives[number] = len(lines[number]) - len(token.content)
        elif token.type == "inline":
            _mask_inline_code(token, lines, masked)
            inline_removals.extend(_inline_removals(token, lines, offsets))
    return code, directives, masked, inline_removals


@dataclass(frozen=True, slots=True)
class Marker:
    ref: str
    kind: DirectiveKind
    start: int
    end: int
    line: int


class ViolationCode(StrEnum):
    INVALID_BLOCK_DIRECTIVE = "invalid_block_directive"
    INLINE_DIRECTIVE = "inline_directive"
    DUPLICATE_DIRECTIVE_ENTRY = "duplicate_directive_entry"
    DUPLICATE_MARKER = "duplicate_marker"
    MARKER_WITHOUT_ENTRY = "marker_without_entry"
    DIRECTIVE_KIND_MISMATCH = "directive_kind_mismatch"
    UNKNOWN_IMAGE = "unknown_image"
    DUPLICATE_IMAGE = "duplicate_image"
    ENTRY_WITHOUT_MARKER = "entry_without_marker"
    TOO_MANY_WIDGETS = "too_many_widgets"
    TOO_MANY_QUIZZES = "too_many_quizzes"
    REPEATED_WIDGET_MODE = "repeated_widget_mode"
    KEY_TERM_ABSENT = "key_term_absent"


@dataclass(frozen=True, slots=True)
class Violation:
    code: ViolationCode
    message: str
    line: int | None = None
    directive_index: int | None = None
    key_term_index: int | None = None


def _scan(markdown: str) -> tuple[list[Marker], list[Violation], list[tuple[int, int]]]:
    markers: list[Marker] = []
    issues: list[Violation] = []
    removals: list[tuple[int, int]] = []
    source = list(_source_lines(markdown))
    lines = [raw.rstrip("\r\n") for raw in source]
    offsets: list[int] = []
    offset = 0
    for raw in source:
        offsets.append(offset)
        offset += len(raw)
    code_lines, block_directives, masked, inline_removals = _markdown_context(markdown, lines, offsets)
    for index, line in enumerate(lines):
        number = index + 1
        start = offsets[index]
        if index in code_lines:
            continue
        column = block_directives.get(index)
        candidate = _CANDIDATE.match(line)
        if column is None and candidate and masked[index][candidate.start(1)] == ":":
            column = candidate.start(1)
        if column is not None:
            match = _DIRECTIVE.fullmatch(line)
            if match and (match[1] == "image") == (match[2] == "id"):
                markers.append(Marker(match[3], cast(DirectiveKind, match[1]), start, start + len(line), number))
            else:
                issues.append(
                    Violation(
                        ViolationCode.INVALID_BLOCK_DIRECTIVE,
                        f"line {number}: directive must be an unindented leaf with only ref or image id",
                        line=number,
                    )
                )
                removals.append((start + column, start + len(line)))
    for start, end, index in inline_removals:
        number = index + 1
        issues.append(
            Violation(
                ViolationCode.INLINE_DIRECTIVE, f"line {number}: inline directives are not supported", line=number
            )
        )
        removals.append((start, end))
    return markers, issues, removals


def extract_markers(markdown: str) -> tuple[list[Marker], list[str]]:
    markers, issues, _ = _scan(markdown)
    return markers, [issue.message for issue in issues]


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
    return [
        issue.message
        for issue in find_violations(
            markdown,
            directives,
            image_aliases=image_aliases,
            max_widgets=max_widgets,
            max_quizzes=max_quizzes,
            alternation=alternation,
            key_terms=key_terms,
        )
    ]


def find_violations(
    markdown: str,
    directives: Sequence[Directive],
    *,
    image_aliases: Collection[str] | None = None,
    max_widgets: int | None = None,
    max_quizzes: int | None = None,
    alternation: bool = False,
    key_terms: Sequence[str] | None = None,
) -> list[Violation]:
    markers, issues, _ = _scan(markdown)
    declared: dict[str, Directive] = {}
    declared_indices: dict[str, int] = {}
    for index, entry in enumerate(directives):
        if entry.ref in declared:
            issues.append(
                Violation(
                    ViolationCode.DUPLICATE_DIRECTIVE_ENTRY,
                    f"duplicate directive ref {entry.ref!r} in the directive list",
                    directive_index=index,
                )
            )
        else:
            declared[entry.ref] = entry
            declared_indices[entry.ref] = index
    seen: set[str] = set()
    images: set[str] = set()
    for marker in markers:
        if marker.ref in seen:
            issues.append(
                Violation(
                    ViolationCode.DUPLICATE_MARKER,
                    f"directive ref {marker.ref!r} appears more than once in the markdown",
                    line=marker.line,
                )
            )
        seen.add(marker.ref)
        target = declared.get(marker.ref)
        if target is None:
            issues.append(
                Violation(
                    ViolationCode.MARKER_WITHOUT_ENTRY,
                    f"markdown directive {marker.ref!r} has no entry in the directive list",
                    line=marker.line,
                )
            )
        elif target.kind != marker.kind:
            issues.append(
                Violation(
                    ViolationCode.DIRECTIVE_KIND_MISMATCH,
                    f"directive {marker.ref!r} has different kinds in markdown and list",
                    line=marker.line,
                )
            )
        if marker.kind == "image":
            if image_aliases is not None and marker.ref not in image_aliases:
                issues.append(
                    Violation(ViolationCode.UNKNOWN_IMAGE, f"unknown image id {marker.ref!r}", line=marker.line)
                )
            if marker.ref in images:
                issues.append(
                    Violation(
                        ViolationCode.DUPLICATE_IMAGE,
                        f"image id {marker.ref!r} is used more than once",
                        line=marker.line,
                    )
                )
            images.add(marker.ref)
    for ref, index in declared_indices.items():
        if ref not in seen:
            issues.append(
                Violation(
                    ViolationCode.ENTRY_WITHOUT_MARKER,
                    f"directive {ref!r} missing from the markdown",
                    directive_index=index,
                )
            )
    for kind, limit, code in (
        ("widget", max_widgets, ViolationCode.TOO_MANY_WIDGETS),
        ("quiz", max_quizzes, ViolationCode.TOO_MANY_QUIZZES),
    ):
        slots = [m for m in markers if m.kind == kind]
        if limit is not None and len(slots) > limit:
            issues.append(
                Violation(code, f"too many {kind} directives: {len(slots)} > {limit}", line=slots[limit].line)
            )
    if alternation:
        widgets = [
            (m, declared[m.ref])
            for m in markers
            if m.kind == "widget" and m.ref in declared and declared[m.ref].kind == "widget"
        ]
        for (_, previous), (marker, current) in pairwise(widgets):
            if (
                previous.primitive_hint is not None
                and previous.mode_hint is not None
                and (previous.primitive_hint, previous.mode_hint) == (current.primitive_hint, current.mode_hint)
            ):
                issues.append(
                    Violation(
                        ViolationCode.REPEATED_WIDGET_MODE,
                        f"widgets {previous.ref!r} and {current.ref!r} have identical primitive and mode",
                        line=marker.line,
                    )
                )
    if key_terms is not None:
        for index, term in enumerate(key_terms):
            if term not in markdown:
                issues.append(
                    Violation(
                        ViolationCode.KEY_TERM_ABSENT,
                        f"key term {term!r} is absent from markdown",
                        key_term_index=index,
                    )
                )
    return issues


def sanitize_draft(
    draft: RecoveredPageDraft, *, max_widgets: int, max_quizzes: int = 5, image_aliases: Collection[str] | None = None
) -> RecoveredPageDraft:
    markers, _, removed = _scan(draft.markdown)
    entries: dict[str, Directive] = {}
    for directive in draft.directives:
        entries.setdefault(directive.ref, directive)
    kept: list[Directive] = []
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
            # Leave the original line ending so adjacent prose and code stay separate.
            removed.append((marker.start, marker.end))
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
    markdown = draft.markdown
    # A malformed block can overlap an inline directive found by CommonMark.
    merged: list[tuple[int, int]] = []
    for start, end in sorted(removed):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    for index in reversed(range(len(merged))):
        start, end = merged[index]
        # Remove the colons of a newly exposed marker; keep whitespace and surrounding text.
        following = re.match(r"([ \t]*)::", markdown[end:])
        replacement = ""
        if following:
            whitespace = following.group(1)
            end += len(whitespace) + 2
            replacement = whitespace
        # Removing an inline directive can expose a literal name on its left,
        # for example :quiz:widget[label]. Keep that literal escaped.
        previous_end = merged[index - 1][1] if index else 0
        prefix = _INLINE_PREFIX.search(markdown, max(previous_end, start - 8), start)
        if prefix and _INLINE_NAME.match(prefix[0] + replacement + markdown[end : end + 8]):
            start = prefix.start()
            replacement = "\\" + prefix[0] + replacement
        markdown = markdown[:start] + replacement + markdown[end:]
    try:
        return RecoveredPageDraft.model_validate(
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
