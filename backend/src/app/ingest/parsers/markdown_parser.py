import base64
import binascii
import re
from contextlib import suppress
from pathlib import PurePosixPath
from string import punctuation

from src.app.exceptions.ingest import ParseError
from src.app.ingest.markdown_syntax import parse_markdown
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
        markers_after: dict[int, list[str]] = {}
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
                # Keep the alt text in the original block so links, headings and
                # table cells retain their structure. Emit the directive after it.
                markers_after.setdefault(block.end, []).append(marker)
            replacements.append((image.start, image.end, replacement))

        for end, markers in markers_after.items():
            prefix = "\n" if text[end - 1 : end] == "\n" else "\n\n"
            replacements.append((end, end, prefix + "\n\n".join(markers) + "\n\n"))
        text = _replace_ranges(text, replacements)
        if any(heading.markup in {"=", "-"} for heading in structure.headings):
            replacements = [
                (heading.start, heading.end, _atx_heading(heading.level, heading.title))
                for heading in parse_markdown(text).headings
                if heading.markup in {"=", "-"}
            ]
            text = _replace_ranges(text, replacements)
        return ParsedDocument(markdown=text, images=tuple(images), title=PurePosixPath(filename).stem)


def _atx_heading(level: int, content: str) -> str:
    title = " ".join(content.splitlines())
    # A closing sequence keeps literal trailing hashes from becoming syntax.
    close = " #" if title.endswith("#") else ""
    return f"{'#' * level} {title}{close}\n"


def _replace_ranges(text: str, replacements: list[tuple[int, int, str]]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(replacements):
        parts.extend((text[cursor:start], replacement))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)
