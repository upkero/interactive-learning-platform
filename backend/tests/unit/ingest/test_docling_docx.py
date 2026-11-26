import json
from pathlib import Path

import pytest

from src.app.ingest.parsers.docling_parser import DoclingParser
from src.app.ingest.topic_tree import build_topic_tree


class Counter:
    def count(self, text: str) -> int:
        return len(text)


@pytest.mark.unit
def test_docx_heading_levels_are_restored() -> None:
    fixture = Path(__file__).parents[2] / "fixtures/documents/headings.docx"
    parsed = DoclingParser().parse(fixture.read_bytes(), filename=fixture.name)
    roots = build_topic_tree(parsed.markdown, Counter())
    assert [(node.title, node.level) for node in roots] == [("Introduction", 1)]
    assert [(node.title, node.level) for node in roots[0].children] == [("Details", 2)]
    assert "#### Deep heading" in parsed.markdown
    assert not roots[0].children[0].children
    expected = json.loads(fixture.with_suffix(".tree.json").read_text(encoding="utf-8"))
    assert [
        {
            "id": root.id,
            "title": root.title,
            "level": root.level,
            "children": [
                {"id": child.id, "title": child.title, "level": child.level, "children": []} for child in root.children
            ],
        }
        for root in roots
    ] == expected
