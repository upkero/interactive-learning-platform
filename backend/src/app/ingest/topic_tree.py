import re
from dataclasses import dataclass, field
from typing import Protocol

from src.app.contracts.documents.topic_node import TopicNode
from src.app.ingest.markdown_syntax import parse_markdown


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


_NUMBERED = re.compile(r"^(\d+(?:\.\d+){0,2})\.?\s+\S")
_CHAPTER = re.compile(r"^(глава|часть|chapter|part)\s+\w+", re.IGNORECASE)
MAX_TREE_LEVEL = 3


@dataclass(slots=True)
class _TopicBuilder:
    id: str
    title: str
    level: int
    start: int
    end: int
    own_tokens: int = 0
    total_tokens: int = 0
    page: int | None = None
    image_ids: list[str] = field(default_factory=list)
    children: list["_TopicBuilder"] = field(default_factory=list)

    def freeze(self) -> TopicNode:
        return TopicNode(
            id=self.id,
            title=self.title,
            level=self.level,
            start=self.start,
            end=self.end,
            own_tokens=self.own_tokens,
            total_tokens=self.total_tokens,
            page=self.page,
            image_ids=tuple(self.image_ids),
            children=tuple(child.freeze() for child in self.children),
        )


def heading_level(title: str, markdown_level: int) -> int:
    numbered = _NUMBERED.match(title.strip())
    if numbered:
        return min(numbered.group(1).count(".") + 1, MAX_TREE_LEVEL)
    if _CHAPTER.match(title.strip()):
        return 1
    return min(markdown_level, MAX_TREE_LEVEL)


def build_topic_tree(
    markdown: str, counter: TokenCounter, heading_pages: tuple[tuple[str, int], ...] = ()
) -> list[TopicNode]:
    structure = parse_markdown(markdown)
    headings = [(item.start, heading_level(item.title, item.level), item.title) for item in structure.headings]
    roots: list[_TopicBuilder] = []
    if not headings or markdown[: headings[0][0]].strip():
        roots.append(
            _TopicBuilder(
                id="0", title="Вступление", level=1, start=0, end=headings[0][0] if headings else len(markdown)
            )
        )
    stack: list[_TopicBuilder] = []
    for index, (start, level, title) in enumerate(headings):
        while stack and stack[-1].level >= level:
            stack.pop()
        siblings = stack[-1].children if stack else roots
        root_count = len([node for node in roots if node.id != "0"])
        node_id = f"{stack[-1].id}.{len(siblings) + 1}" if stack else str(root_count + 1)
        end = next((pos for pos, next_level, _ in headings[index + 1 :] if next_level <= level), len(markdown))
        if not roots and not stack and not markdown[:start].strip():
            start = 0
        node = _TopicBuilder(id=node_id, title=title, level=level, start=start, end=end)
        for page_index, (page_title, page) in enumerate(heading_pages):
            if page_title.casefold() == title.casefold():
                node.page = page
                heading_pages = heading_pages[page_index + 1 :]
                break
        siblings.append(node)
        stack.append(node)
    for root in roots:
        _fill(root, markdown, counter, structure.markers)
    return [root.freeze() for root in roots]


def _fill(node: _TopicBuilder, markdown: str, counter: TokenCounter, markers: tuple[tuple[int, str], ...]) -> int:
    own_end = node.children[0].start if node.children else node.end
    own_text = markdown[node.start : own_end]
    node.own_tokens = counter.count(own_text)
    node.total_tokens = node.own_tokens + sum(_fill(child, markdown, counter, markers) for child in node.children)
    node.image_ids = [ref for position, ref in markers if node.start <= position < own_end]
    return node.total_tokens
