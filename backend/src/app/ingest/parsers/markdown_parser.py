import base64
import binascii
import re
from pathlib import PurePosixPath

from src.app.ingest.parsers.base import DocumentParser, ExtractedImage, ParsedDocument

_IMAGE = re.compile(r"!\[([^]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_DATA = re.compile(r"^data:(image/(?:png|jpeg|jpg|gif|webp));base64,(.+)$", re.IGNORECASE | re.DOTALL)


class MarkdownParser(DocumentParser):
    supported_mime_types = frozenset({"text/markdown", "text/plain"})

    def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
        text = data.decode("utf-8-sig")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.splitlines()
        result: list[str] = []
        in_fence = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
                in_fence = not in_fence
            if not in_fence and i + 1 < len(lines) and line.strip() and re.fullmatch(r"\s*(=+|-+)\s*", lines[i + 1]):
                result.append(f"{'#' if lines[i + 1].strip()[0] == '=' else '##'} {line.strip()}")
                i += 2
                continue
            result.append(line)
            i += 1
        normalized = "\n".join(result)
        if text.endswith("\n"):
            normalized += "\n"

        images: list[ExtractedImage] = []
        counter = 0

        def replace(match: re.Match[str]) -> str:
            nonlocal counter
            if in_code_at(normalized, match.start()):
                return match.group(0)
            source = match.group(2)
            data_match = _DATA.match(source)
            if data_match is None:
                return match.group(1) or source
            try:
                raw = base64.b64decode(data_match.group(2), validate=True)
            except (binascii.Error, ValueError):
                return match.group(1) or source
            counter += 1
            ref = f"img_{counter}"
            media_type = data_match.group(1).lower().replace("jpg", "jpeg")
            images.append(ExtractedImage(ref=ref, data=raw, media_type=media_type, caption=match.group(1) or None))
            return f'\n::image{{id="{ref}"}}\n'

        normalized = _IMAGE.sub(replace, normalized)
        return ParsedDocument(markdown=normalized, images=tuple(images), title=PurePosixPath(filename).stem)


def in_code_at(text: str, position: int) -> bool:
    return sum(1 for line in text[:position].splitlines() if line.lstrip().startswith(("```", "~~~"))) % 2 == 1
