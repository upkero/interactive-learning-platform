import base64

import pytest

from src.app.ingest.markdown_syntax import parse_markdown
from src.app.ingest.parsers.markdown_parser import MarkdownParser
from src.app.ingest.topic_tree import build_topic_tree


class Counter:
    def count(self, text: str) -> int:
        return len(text)


@pytest.mark.unit
def test_code_images_four_backtick_fences_indented_heading_and_table_are_preserved() -> None:
    source = (
        "Example: `![sample](https://example.org/img.png)`\n\n"
        "````\n```\n# Example inside code\nTitle inside code\n---\n```\n````\n\n"
        "  ## Real topic\n\n| key | value |\n| --- | --- |\n| a | b |\n"
    )
    parsed = MarkdownParser().parse(source.encode(), filename="sample.md")
    assert parsed.markdown == source
    assert parsed.images == ()
    assert [node.title for node in build_topic_tree(parsed.markdown, Counter())] == ["Вступление", "Real topic"]
    structure = parse_markdown(parsed.markdown)
    assert len(structure.headings) == 1
    assert structure.images == ()


@pytest.mark.unit
def test_data_image_inside_table_keeps_table_delimiters_and_inline_code_unchanged() -> None:
    png = base64.b64encode(b"png data").decode()
    source = (
        "| image | example |\n| --- | --- |\n"
        f"| ![diagram](data:image/png;base64,{png}) | `![fake](data:image/png;base64,{png})` |\n"
    )
    parsed = MarkdownParser().parse(source.encode(), filename="table.md")
    assert len(parsed.images) == 1
    expected_table = source.replace(f"![diagram](data:image/png;base64,{png})", "diagram")
    assert parsed.markdown.startswith(expected_table + "\n")
    assert parsed.markdown.splitlines()[-2] == '::image{id="img_1"}'
    structure = parse_markdown(parsed.markdown)
    assert structure.blocks[0].kind == "table_open"
    assert len(structure.markers) == 1


def test_protected_blocks_match_full_parser_for_repeated_fences() -> None:
    from src.app.ingest.markdown_syntax import parse_markdown, protected_markdown_blocks

    text = ("Explanation.\n\n```python\nprint('hello')\n```\n\n" * 10) + (
        "Other explanation.\n\n~~~~\nline\n```\n~~~~\n\n"
    )
    assert protected_markdown_blocks(text) == parse_markdown(text).protected_blocks
