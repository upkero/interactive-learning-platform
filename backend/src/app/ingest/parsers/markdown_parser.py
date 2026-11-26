import base64
import binascii
import re
from bisect import bisect_left, bisect_right
from contextlib import suppress
from dataclasses import replace
from itertools import accumulate
from pathlib import PurePosixPath
from string import punctuation

from src.app.exceptions.ingest import ParseError
from src.app.ingest.markdown_syntax import Block, Image, parse_markdown
from src.app.ingest.parsers.base import DocumentParser, ExtractedImage, ParsedDocument

_DATA = re.compile(r"^data:(image/(?:png|jpeg|jpg|gif|webp));base64,(.+)$", re.IGNORECASE | re.DOTALL)
_ALT_PUNCTUATION = re.compile(f"[{re.escape(punctuation)}]")


class MarkdownParser(DocumentParser):
    """Normalize Markdown headings and extract embedded images."""

    supported_mime_types = frozenset({"text/markdown", "text/plain"})

    def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParseError("Markdown must be UTF-8") from exc
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        structure = parse_markdown(text, extract_images=True)
        images: list[ExtractedImage] = []
        replacements = [(start, start, "\\") for start, _ in structure.markers]
        inline_images: dict[str, tuple[Image, int]] = {}
        for image in structure.images:
            alt = _ALT_PUNCTUATION.sub(
                lambda match: "\\" + match[0],
                " ".join(image.caption.split()),
            )
            data_match = _DATA.fullmatch(image.source)
            raw: bytes | None = None
            if data_match is not None:
                with suppress(binascii.Error, ValueError):
                    raw = base64.b64decode(data_match[2], validate=True)
            replacement = alt
            if data_match is not None and raw:
                ref = f"img_{len(images) + 1}"
                media_type = data_match[1].lower().replace("jpg", "jpeg")
                images.append(ExtractedImage(ref=ref, data=raw, media_type=media_type, caption=image.caption or None))
                marker = f'::image{{id="{ref}"}}'
                block = image.block
                if (
                    block.kind == "paragraph_open"
                    and text[block.start : block.end].strip() == text[image.start : image.end]
                ):
                    prefix = "\n" if block.start and text[block.start - 2 : block.start] != "\n\n" else ""
                    suffix = "\n\n" if block.end < len(text) else "\n"
                    replacements.append((block.start, block.end, f"{prefix}{marker}{suffix}"))
                    continue
                inline_images[ref] = (image, len(alt))
            replacements.append((image.start, image.end, replacement))

        has_setext = any(heading.markup in {"=", "-"} for heading in structure.headings)
        text = _replace_ranges(text, replacements)
        if inline_images or has_setext:
            normalized = parse_markdown(text)
            edits, spans = _inline_marker_edits(text, normalized.blocks, replacements, inline_images)
            if spans:
                images = [replace(image, paragraph_span=spans.get(image.ref)) for image in images]
            if has_setext:
                edits.extend(
                    (heading.start, heading.end, _atx_heading(heading.level, heading.title))
                    for heading in normalized.headings
                    if heading.markup in {"=", "-"}
                )
            text = _replace_ranges(text, edits)
        return ParsedDocument(markdown=text, images=tuple(images), title=PurePosixPath(filename).stem)


def _atx_heading(level: int, content: str) -> str:
    title = " ".join(content.splitlines())
    # A closing sequence keeps literal trailing hashes from becoming syntax.
    close = " #" if title.endswith("#") else ""
    return f"{'#' * level} {title}{close}\n"


def _inline_marker_edits(
    text: str,
    blocks: tuple[Block, ...],
    replacements: list[tuple[int, int, str]],
    images: dict[str, tuple[Image, int]],
) -> tuple[list[tuple[int, int, str]], dict[str, tuple[int, int]]]:
    # Removing an empty alt can split a source paragraph. Find the block
    # containing each replacement before adding any image directives.
    changes = sorted((end, len(value) - (end - start)) for start, end, value in replacements)
    ends = [end for end, _ in changes]
    shifts = (0, *accumulate(delta for _, delta in changes))
    insertions = {start: len(value) for start, end, value in replacements if start == end}
    block_starts = [block.start for block in blocks]

    def translated(position: int) -> int:
        return position + shifts[bisect_right(ends, position)]

    markers_after: dict[int, list[str]] = {}
    spans: dict[str, tuple[int, int]] = {}
    for ref, (image, alt_length) in images.items():
        start = translated(image.block.start)
        end = translated(image.block.end) - insertions.get(image.block.end, 0)
        position = translated(image.start)
        first = bisect_left(block_starts, start)
        limit = bisect_left(block_starts, end)
        if first < limit:
            index = bisect_right(block_starts, position, first, limit) - 1
            if index < first or (blocks[index].end <= position and index + 1 < limit):
                index += 1
            owner = blocks[index]
            end = owner.end
            if owner.kind == "paragraph_open":
                offset = min(max(position, owner.start), end) - owner.start
                spans[ref] = (offset, offset + alt_length)
        markers_after.setdefault(end, []).append(f'::image{{id="{ref}"}}')

    edits = []
    for end, markers in markers_after.items():
        prefix = "\n" if text[end - 1 : end] == "\n" else "\n\n"
        edits.append((end, end, prefix + "\n\n".join(markers) + "\n\n"))
    return edits, spans


def _replace_ranges(text: str, replacements: list[tuple[int, int, str]]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(replacements):
        parts.extend((text[cursor:start], replacement))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)
