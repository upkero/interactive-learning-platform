import re
from dataclasses import dataclass, field

from src.app.ingest.tokens import TokenCounter

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$", re.MULTILINE)
_NUMBERED = re.compile(r"^(\d+(?:\.\d+){0,2})\.?\s+\S")
_CHAPTER = re.compile(r"^(глава|часть|chapter|part)\s+\w+", re.IGNORECASE)
_IMAGE = re.compile(r'::image\{id="(img_\d+)"\}')
MAX_TREE_LEVEL = 3


@dataclass(slots=True)
class TopicNode:
    id: str
    title: str
    level: int
    start: int
    end: int
    own_tokens: int = 0
    total_tokens: int = 0
    page: int | None = None
    image_ids: list[str] = field(default_factory=list)
    children: list["TopicNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "start": self.start,
            "end": self.end,
            "own_tokens": self.own_tokens,
            "total_tokens": self.total_tokens,
            "page": self.page,
            "image_ids": self.image_ids,
            "children": [child.to_dict() for child in self.children],
        }


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
    headings = [
        (m.start(), heading_level(m.group(2), len(m.group(1))), m.group(2).strip())
        for m in _HEADING.finditer(markdown)
        if not _inside_code_fence(markdown, m.start())
    ]
    roots: list[TopicNode] = []
    if not headings or headings[0][0] > 0:
        roots.append(TopicNode("0", "Вступление", 1, 0, headings[0][0] if headings else len(markdown)))
    stack: list[TopicNode] = []
    for index, (start, level, title) in enumerate(headings):
        while stack and stack[-1].level >= level:
            stack.pop()
        siblings = stack[-1].children if stack else roots
        root_count = len([node for node in roots if node.id != "0"])
        node_id = f"{stack[-1].id}.{len(siblings) + 1}" if stack else str(root_count + 1)
        end = next((pos for pos, next_level, _ in headings[index + 1 :] if next_level <= level), len(markdown))
        node = TopicNode(node_id, title, level, start, end)
        siblings.append(node)
        stack.append(node)
    page_by_title = {title.casefold(): page for title, page in heading_pages}
    for root in roots:
        _fill(root, markdown, counter, page_by_title)
    return roots


def _fill(node: TopicNode, markdown: str, counter: TokenCounter, page_by_title: dict[str, int]) -> int:
    own_end = node.children[0].start if node.children else node.end
    own_text = markdown[node.start : own_end]
    node.own_tokens = counter.count(own_text)
    node.total_tokens = node.own_tokens + sum(_fill(child, markdown, counter, page_by_title) for child in node.children)
    node.image_ids = _IMAGE.findall(own_text)
    node.page = page_by_title.get(node.title.casefold())
    return node.total_tokens


def _inside_code_fence(markdown: str, position: int) -> bool:
    return sum(1 for line in markdown[:position].splitlines() if line.lstrip().startswith(("```", "~~~"))) % 2 == 1
