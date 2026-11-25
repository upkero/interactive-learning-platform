import re
from io import BytesIO
from threading import Lock

from pypdf import PdfReader

from src.app.exceptions.ingest import ParseError
from src.app.ingest.parsers.base import DocumentParser, ExtractedImage, ParsedDocument

_PLACEHOLDER = "<!-- grasp:image -->"


class DoclingParser(DocumentParser):
    supported_mime_types = frozenset(
        {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    )

    def __init__(self, *, images_scale: float = 2.0, artifacts_path: str | None = None) -> None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions(
            generate_picture_images=True,
            images_scale=images_scale,
            do_ocr=False,
            artifacts_path=artifacts_path,
        )
        self._converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        self._conversion_lock = Lock()

    def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
        from docling.datamodel.base_models import DocumentStream
        from docling_core.types.doc.items.text import SectionHeaderItem

        try:
            # The converter caches pipelines; do not initialize/use the same
            # pipeline concurrently when multiple tasks run in one worker.
            with self._conversion_lock:
                result = self._converter.convert(DocumentStream(name=filename, stream=BytesIO(data)))
            doc = result.document
            markdown = doc.export_to_markdown(image_placeholder=_PLACEHOLDER)
        except Exception as exc:
            raise ParseError("Docling failed to convert document") from exc
        images: list[ExtractedImage] = []
        heading_pages: list[tuple[str, int]] = []
        headers: list[tuple[str, int]] = []
        for obj, _ in doc.iterate_items():
            if isinstance(obj, SectionHeaderItem):
                text = obj.text.strip()
                prov = obj.prov
                if text and prov:
                    heading_pages.append((text, int(prov[0].page_no)))
                if text:
                    headers.append((text, obj.level))
        if filename.lower().endswith(".docx"):
            header_index = 0

            def restore_level(match: re.Match[str]) -> str:
                nonlocal header_index
                if header_index >= len(headers):
                    return match.group(0)
                text, level = headers[header_index]
                if match.group(2).strip() != text:
                    return match.group(0)
                header_index += 1
                return f"{'#' * max(1, level)} {match.group(2)}"

            markdown = re.sub(r"^(#{1,6})\s+(.+)$", restore_level, markdown, flags=re.MULTILINE)
        for index, picture in enumerate(doc.pictures, start=1):
            image = picture.get_image(doc)
            if image is None:
                markdown = markdown.replace(_PLACEHOLDER, "", 1)
                continue
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            prov = picture.prov
            caption = picture.caption_text(doc) or None
            ref = f"img_{index}"
            markdown = markdown.replace(_PLACEHOLDER, f'\n::image{{id="{ref}"}}\n', 1)
            images.append(
                ExtractedImage(
                    ref=ref,
                    data=buffer.getvalue(),
                    media_type="image/png",
                    page=int(prov[0].page_no) if prov else None,
                    caption=caption,
                )
            )
        if filename.lower().endswith(".pdf") and not heading_pages:
            markdown, heading_pages = _recover_numbered_pdf_headings(data, markdown, images)
        page_count = len(doc.pages) or None
        return ParsedDocument(
            markdown=markdown,
            images=tuple(images),
            page_count=page_count,
            title=None,
            heading_pages=tuple(heading_pages),
        )


_NUMBERED_PAGE_HEADING = re.compile(r"^(?:\d+(?:\.\d+){0,2}\.?\s+\S|(?:chapter|part|глава|часть)\s+\S)", re.I)


def _recover_numbered_pdf_headings(
    data: bytes, markdown: str, images: list[ExtractedImage]
) -> tuple[str, list[tuple[str, int]]]:
    """Recover page headings Docling's layout model silently omits.

    Only use numbered first lines actually present in the PDF text layer;
    anchor them to the corresponding page's body (or first picture). Never
    manufacture a heading when a page cannot be aligned to the export.
    """
    insertions: list[tuple[int, str]] = []
    headings: list[tuple[str, int]] = []
    cursor = 0
    for page_number, page in enumerate(PdfReader(BytesIO(data)).pages, 1):
        lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line.strip()]
        if len(lines) < 2 or not _NUMBERED_PAGE_HEADING.match(lines[0]):
            continue
        anchor = markdown.find(lines[1], cursor)
        if anchor < 0:
            continue
        position = anchor
        first_picture = next((image for image in images if image.page == page_number), None)
        if first_picture is not None:
            marker = markdown.find(f'::image{{id="{first_picture.ref}"}}', cursor)
            if cursor <= marker < anchor:
                position = marker
        if position < cursor:
            continue
        prefix = "" if position == 0 or markdown[position - 1] == "\n" else "\n\n"
        insertions.append((position, f"{prefix}## {lines[0]}\n\n"))
        headings.append((lines[0], page_number))
        cursor = anchor + len(lines[1])
    for position, heading in reversed(insertions):
        markdown = markdown[:position] + heading + markdown[position:]
    return markdown, headings
