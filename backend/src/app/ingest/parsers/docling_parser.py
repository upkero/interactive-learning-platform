from io import BytesIO

from src.app.ingest.parsers.base import DocumentParser, ExtractedImage, ParsedDocument

_PLACEHOLDER = "<!-- grasp:image -->"


class DoclingParser(DocumentParser):
    supported_mime_types = frozenset(
        {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    )

    def __init__(self, *, images_scale: float = 2.0) -> None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions(generate_picture_images=True, images_scale=images_scale)
        self._converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})

    def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
        from docling.document_converter import DocumentStream  # type: ignore[attr-defined]

        try:
            result = self._converter.convert(DocumentStream(name=filename, stream=BytesIO(data)))
            doc = result.document
            markdown = doc.export_to_markdown(image_placeholder=_PLACEHOLDER)
        except Exception as exc:
            raise ValueError("Docling failed to convert document") from exc
        images: list[ExtractedImage] = []
        heading_pages: list[tuple[str, int]] = []
        for item in getattr(doc, "iterate_items", lambda: ())():
            obj = item[0] if isinstance(item, tuple) else item
            if getattr(obj, "label", None) == "section_header":
                text = str(getattr(obj, "text", "")).strip()
                prov = getattr(obj, "prov", ())
                if text and prov:
                    heading_pages.append((text, int(prov[0].page_no)))
        for index, picture in enumerate(getattr(doc, "pictures", ()), start=1):
            image = picture.get_image(doc)
            if image is None:
                markdown = markdown.replace(_PLACEHOLDER, "", 1)
                continue
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            prov = getattr(picture, "prov", ())
            caption = picture.caption_text(doc) or None
            ref = f"img_{index}"
            markdown = markdown.replace(_PLACEHOLDER, f'\n::image{{id="{ref}"}}\n', 1)
            images.append(
                ExtractedImage(ref, buffer.getvalue(), "image/png", int(prov[0].page_no) if prov else None, caption)
            )
        page_count = len(getattr(doc, "pages", ())) or None
        return ParsedDocument(
            markdown=markdown,
            images=tuple(images),
            page_count=page_count,
            title=None,
            heading_pages=tuple(heading_pages),
        )
