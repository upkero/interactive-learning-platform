import json
from itertools import pairwise
from pathlib import Path

import pytest

from src.app.contracts.documents.topic_node import TopicNode
from src.app.ingest.topic_tree import build_topic_tree


class Count:
    def count(self, value: str) -> int:
        return len(value)


@pytest.mark.unit
def test_builds_numbered_tree_and_ignores_fenced_headings() -> None:
    markdown = "intro\n\n## 1 Chapter\ntext\n### 1.1 Part\nbody\n```\n# ignored\n```\n## 2 Next\n"
    roots = build_topic_tree(markdown, Count())
    assert [root.id for root in roots] == ["0", "1", "2"]
    assert roots[1].level == 1
    assert roots[1].children[0].id == "1.1"
    assert roots[1].total_tokens == roots[1].own_tokens + roots[1].children[0].total_tokens
    assert roots[1].own_tokens == len(markdown[roots[1].start : roots[1].children[0].start])


@pytest.mark.unit
def test_indented_heading_and_nested_image_ownership() -> None:
    markdown = '# Main\nparent\n\n  ## Child\n::image{id="img_1"}\n\n#### Deep\n'
    roots = build_topic_tree(markdown, Count())
    assert len(roots) == 1
    parent, child = roots[0], roots[0].children[0]
    assert parent.own_tokens == len(markdown[parent.start : child.start])
    assert parent.image_ids == ()
    assert child.image_ids == ("img_1",)
    assert child.total_tokens == child.own_tokens == len(markdown[child.start : child.end])


@pytest.mark.unit
def test_deep_headings_whitespace_and_repeated_pages() -> None:
    markdown = "\n# Same\n## Detail\n#### Deep\nbody\n# Same\n"
    roots = build_topic_tree(markdown, Count(), (("Same", 4), ("Detail", 5), ("Same", 9)))
    assert [node.title for node in roots] == ["Same", "Same"]
    assert [node.page for node in roots] == [4, 9]
    assert roots[0].start == 0 and roots[-1].end == len(markdown)
    assert roots[0].children[0].title == "Detail"
    assert not roots[0].children[0].children
    assert "#### Deep" in markdown[roots[0].children[0].start : roots[0].children[0].end]


@pytest.mark.unit
@pytest.mark.parametrize("name", ["course_ru", "course_en"])
def test_tree_matches_golden_fixture(name: str) -> None:
    directory = Path(__file__).parents[2] / "fixtures/documents"
    markdown = (directory / f"{name}.md").read_text(encoding="utf-8")
    roots = build_topic_tree(markdown, Count())

    def summary(node: TopicNode) -> dict[str, object]:
        assert node.total_tokens == node.own_tokens + sum(child.total_tokens for child in node.children)
        return {
            "id": node.id,
            "title": node.title,
            "level": node.level,
            "children": [summary(child) for child in node.children],
        }

    assert [summary(node) for node in roots] == json.loads((directory / f"{name}.tree.json").read_text())
    assert roots[0].start == 0 and roots[-1].end == len(markdown)
    assert all(first.end == second.start for first, second in pairwise(roots))
