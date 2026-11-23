import base64

import pytest

from src.app.ingest.parsers.markdown_parser import MarkdownParser


@pytest.mark.unit
def test_normalizes_setext_and_preserves_code_and_external_images() -> None:
    source = "Title\n=====\n\n```md\n# not a heading\n![code](data:image/png;base64,AAAA)\n```\n\n![external](https://example.com/a.png)\n"
    parsed = MarkdownParser().parse(source.encode(), filename="lesson.md")
    assert "# Title" in parsed.markdown
    assert "# not a heading" in parsed.markdown
    assert "external" in parsed.markdown
    assert parsed.images == ()


@pytest.mark.unit
def test_extracts_data_image() -> None:
    payload = base64.b64encode(b"image").decode()
    parsed = MarkdownParser().parse(f"![schema](data:image/png;base64,{payload})".encode(), filename="x.md")
    assert '::image{id="img_1"}' in parsed.markdown
    assert parsed.images[0].caption == "schema"
