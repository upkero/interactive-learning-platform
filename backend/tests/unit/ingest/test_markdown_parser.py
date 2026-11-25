import base64

import pytest

from src.app.ingest.markdown_syntax import parse_markdown
from src.app.ingest.parsers.markdown_parser import MarkdownParser
from src.app.ingest.tokens import TokenCounter
from src.app.ingest.topic_tree import build_topic_tree


@pytest.mark.unit
def test_normalizes_setext_and_preserves_code_and_external_images() -> None:
    source = "Title\n=====\n\n```md\n# not a heading\n![code](data:image/png;base64,AAAA)\n```\n\n![external](https://example.com/a.png)\n"
    parsed = MarkdownParser().parse(source.encode(), filename="lesson.md")
    assert "# Title" in parsed.markdown
    assert "# not a heading" in parsed.markdown
    assert parsed.markdown.endswith("\n\nexternal\n")
    assert parsed.images == ()


@pytest.mark.unit
def test_extracts_data_image() -> None:
    payload = base64.b64encode(b"image").decode()
    parsed = MarkdownParser().parse(f"![schema](data:image/png;base64,{payload})".encode(), filename="x.md")
    assert '::image{id="img_1"}' in parsed.markdown
    assert parsed.images[0].caption == "schema"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("source", "expected", "title"),
    [
        ("# Chapter\n---\nText\n", "# Chapter\n---\nText\n", "Chapter"),
        ("First line\nsecond line\n===\nBody\n", "# First line second line\nBody\n", "First line second line"),
    ],
)
def test_heading_kind_and_full_range(source: str, expected: str, title: str) -> None:
    parsed = MarkdownParser().parse(source.encode(), filename="x.md")
    assert parsed.markdown == expected
    (node,) = build_topic_tree(parsed.markdown, TokenCounter())
    assert (node.title, node.level, node.start, node.end) == (title, 1, 0, len(expected))


@pytest.mark.unit
def test_only_extracted_images_become_standalone_directives() -> None:
    image = "![diagram](data:image/png;base64,AAAA)"
    source = f'# Topic\n\n\\{image}\n\nBefore {image} after.\n\n::image{{id="img_99"}}\n\n::image{{id="img_1"}}\n'
    parsed = MarkdownParser().parse(source.encode(), filename="x.md")
    assert f"\\{image}" in parsed.markdown
    assert "Before diagram after." in parsed.markdown.splitlines()
    assert parsed.markdown.splitlines().count('::image{id="img_1"}') == 1
    assert '\\::image{id="img_99"}' in parsed.markdown
    assert [image.ref for image in parsed.images] == ["img_1"]
    (node,) = build_topic_tree(parsed.markdown, TokenCounter())
    assert node.image_ids == ("img_1",)


@pytest.mark.unit
def test_marker_in_multiline_inline_code_is_preserved() -> None:
    source = 'Example: `begin\n::image{id="img_99"}\nend`\n'
    parsed = MarkdownParser().parse(source.encode(), filename="x.md")
    assert parsed.markdown == source
    assert parse_markdown(parsed.markdown).markers == ()


@pytest.mark.unit
def test_marker_in_multiline_alt_does_not_overlap_image_replacement() -> None:
    source = 'Image ![alt\n::image{id="img_88"}\ntext](data:image/png;base64,AAAA)\n'
    parsed = MarkdownParser().parse(source.encode(), filename="x.md")
    assert parsed.images[0].caption == 'alt\n::image{id="img_88"}\ntext'
    assert {ref for _, ref in parse_markdown(parsed.markdown).markers} == {"img_1"}
    assert "data:image" not in parsed.markdown
