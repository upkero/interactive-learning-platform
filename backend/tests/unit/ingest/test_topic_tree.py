import pytest

from src.app.ingest.topic_tree import build_topic_tree


class Count:
    def count(self, value: str) -> int:
        return len(value)


@pytest.mark.unit
def test_builds_numbered_tree_and_ignores_fenced_headings() -> None:
    markdown = "intro\n\n## 1 Chapter\ntext\n### 1.1 Part\nbody\n```\n# ignored\n```\n## 2 Next\n"
    roots = build_topic_tree(markdown, Count())  # type: ignore[arg-type]
    assert [root.id for root in roots] == ["0", "1", "2"]
    assert roots[1].level == 1
    assert roots[1].children[0].id == "1.1"
    assert roots[1].total_tokens == roots[1].own_tokens + roots[1].children[0].total_tokens
