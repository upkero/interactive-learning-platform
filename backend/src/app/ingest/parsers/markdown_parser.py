import base64
import binascii
import re
from pathlib import PurePosixPath

from src.app.exceptions.ingest import ParseError
from src.app.ingest.markdown_syntax import parse_markdown
from src.app.ingest.parsers.base import DocumentParser, ExtractedImage, ParsedDocument

_DATA = re.compile(r"^data:(image/(?:png|jpeg|jpg|gif|webp));base64,(.+)$", re.IGNORECASE | re.DOTALL)


class MarkdownParser(DocumentParser):
    supported_mime_types = frozenset({"text/markdown", "text/plain"})

    def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParseError("Markdown must be UTF-8") from exc
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.splitlines()
        result: list[str] = []
        structure = parse_markdown(text)
        setext_lines = {heading.start: heading.level for heading in structure.headings}
        offset = 0
        i = 0
        while i < len(lines):
            line = lines[i]
            # Markdown-it determines heading positions, including fence lengths.
            if (
                i + 1 < len(lines)
                and line.strip()
                and not re.match(r"^\s{0,3}(?:[-+*]\s|\d+[.)]\s)", line)
                and re.fullmatch(r"\s*(=+|-+)\s*", lines[i + 1])
                and offset in setext_lines
            ):
                result.append(f"{'#' if lines[i + 1].strip()[0] == '=' else '##'} {line.strip()}")
                offset += len(line) + len(lines[i + 1]) + 2
                i += 2
                continue
            result.append(line)
            offset += len(line) + 1
            i += 1
        normalized = "\n".join(result)
        if text.endswith("\n"):
            normalized += "\n"

        images: list[ExtractedImage] = []
        counter = 0

        replacements: list[tuple[int, int, str]] = []
        for image in parse_markdown(normalized).images:
            source = image.source
            data_match = _DATA.match(source)
            if data_match is None:
                continue
            try:
                raw = base64.b64decode(data_match.group(2), validate=True)
            except (binascii.Error, ValueError):
                continue
            counter += 1
            ref = f"img_{counter}"
            media_type = data_match.group(1).lower().replace("jpg", "jpeg")
            images.append(ExtractedImage(ref=ref, data=raw, media_type=media_type, caption=image.caption or None))
            replacements.append((image.start, image.end, f'::image{{id="{ref}"}}'))

        for start, end, replacement in reversed(replacements):
            normalized = normalized[:start] + replacement + normalized[end:]
        return ParsedDocument(markdown=normalized, images=tuple(images), title=PurePosixPath(filename).stem)
