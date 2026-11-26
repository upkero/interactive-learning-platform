"""Regression tests for topic traversal and Markdown boundaries."""

from random import Random
from time import perf_counter
from unittest.mock import patch

import pytest

from src.app.contracts.documents import TopicNode
from src.app.ingest.splitting import SplitLimits, collect_units, split_by_paragraphs, split_document
from src.app.ingest.tokens import TokenCounter, get_token_counter
from src.app.ingest.topic_tree import build_topic_tree

pytestmark = pytest.mark.unit
COUNTER = get_token_counter()
DEFAULT_LIMITS = SplitLimits(15_000, 22_000)
PARAGRAPH = "The lesson explains how a concept changes when its input changes. "


def test_empty_selection_has_no_parts() -> None:
    assert split_document((), set(), "", COUNTER, DEFAULT_LIMITS) == []


def test_empty_source_range_has_no_paragraphs() -> None:
    assert split_by_paragraphs("outside range", 3, 3, COUNTER, DEFAULT_LIMITS) == []


@pytest.mark.parametrize("nested", [False, True])
def test_large_fence_remains_intact_with_following_image(nested: bool) -> None:
    indent = "    " if nested else ""
    prefix = "- A list item\n\n" if nested else ""
    code = indent + "```python\n" + (indent + "print('hello world')\n\n") * 800 + indent + "```\n"
    marker = '\n::image{id="img_1"}\n'
    markdown = prefix + code + ("" if nested else marker)
    maximum = COUNTER.count(code) + 1
    assert maximum < COUNTER.count(markdown)
    tree = build_topic_tree(markdown, COUNTER)
    plans = split_document(tree, {"0"}, markdown, COUNTER, SplitLimits(maximum // 2, maximum))
    assert len(plans) >= 2
    assert "".join(plan.markdown for plan in plans) == markdown
    assert sum(code in plan.markdown for plan in plans) == 1
    assert all(plan.tokens <= maximum for plan in plans)


def test_fence_in_blockquote_remains_whole() -> None:
    code = "> ```python\n" + ("> print('hello world')\n>\n") * 1800 + "> ```\n"
    markdown = code + "\n" + PARAGRAPH * 1300
    maximum = COUNTER.count(code) + 1
    tree = build_topic_tree(markdown, COUNTER)
    assert tree[0].total_tokens > maximum
    plans = split_document(tree, {"0"}, markdown, COUNTER, SplitLimits(maximum // 2, maximum))
    assert "".join(plan.markdown for plan in plans) == markdown
    assert sum(code in part.markdown for part in plans) == 1
    assert all(part.tokens <= maximum for part in plans)


def test_many_short_code_blocks_split_in_under_one_second() -> None:
    block = "Explanation for this example.\n\n```python\nprint('hello')\n```\n\n"
    markdown = block * round(30_000_000 / COUNTER.count(block * 100))
    tree = build_topic_tree(markdown, COUNTER)
    assert 295_000 < tree[0].total_tokens < 305_000
    started = perf_counter()
    plans = split_document(tree, {"0"}, markdown, COUNTER, DEFAULT_LIMITS)
    elapsed = perf_counter() - started
    assert elapsed < 1, f"{elapsed:.3f}s to split {tree[0].total_tokens} tokens"
    assert "".join(part.markdown for part in plans) == markdown
    assert all(part.tokens <= DEFAULT_LIMITS.maximum for part in plans)


def test_selected_child_keeps_the_chapter_id_and_parent_selection_deduplicates() -> None:
    markdown = "# Root\n\nText.\n\n## Child\n\nMore text."
    tree = build_topic_tree(markdown, COUNTER)
    assert collect_units(tree, {"1.1"}, markdown, COUNTER, DEFAULT_LIMITS)[0].chapter_id == "1"
    assert split_document(tree, {"1", "1.1"}, markdown, COUNTER, DEFAULT_LIMITS) == split_document(
        tree, {"1"}, markdown, COUNTER, DEFAULT_LIMITS
    )


def test_large_chapter_heading_stays_with_its_first_subsection() -> None:
    short = "# Short\n\nSmall.\n\n"
    large = "# Long\n\n## Large subsection\n\n" + "word " * 30
    markdown = short + large
    tree = build_topic_tree(markdown, COUNTER)
    plans = split_document(tree, {"1", "2"}, markdown, COUNTER, SplitLimits(25, 40))
    assert plans[0].markdown == short
    assert plans[1].markdown.startswith("# Long\n\n## Large subsection\n\nword")
    assert plans[1].topic_ids == ("2", "2.1")
    assert "".join(plan.markdown for plan in plans) == markdown


@pytest.mark.parametrize("with_children", [False, True])
def test_sixty_thousand_token_topic_preserves_every_range(with_children: bool) -> None:
    paragraph = PARAGRAPH * 12 + "\n\n"
    paragraphs = paragraph * (60_000 // COUNTER.count(paragraph))
    markdown = "# Large topic\n\n"
    if with_children:
        markdown += paragraphs + "## First section\n\n" + paragraphs + "## Second section\n\n" + paragraphs
    else:
        markdown += paragraphs
    tree = build_topic_tree(markdown, COUNTER)
    assert tree[0].total_tokens > DEFAULT_LIMITS.maximum
    units = collect_units(tree, {"1"}, markdown, COUNTER, DEFAULT_LIMITS)
    assert "".join(markdown[unit.start : unit.end] for unit in units) == markdown
    assert all(unit.tokens <= DEFAULT_LIMITS.target for unit in units)
    assert {unit.topic_id for unit in units} == ({"1", "1.1", "1.2"} if with_children else {"1"})


@pytest.mark.parametrize(
    ("block", "target", "maximum"),
    [
        (
            "````python\nalpha = 1\n~~~\n\nbeta = 2\n```\n\nprint(alpha)\n````\n",
            15,
            40,
        ),
        ("| A | B |\n| --- | --- |\n| x. y. | z |\n", 20, 30),
    ],
    ids=["mixed-and-short-fences", "table-with-sentence-boundaries"],
)
def test_code_and_table_stay_whole_after_a_large_paragraph(block: str, target: int, maximum: int) -> None:
    markdown = "A preceding sentence. " * 30 + "\n" + ("\n" if block.startswith("`") else "") + block + "\nAfter.\n"
    assert COUNTER.count(block) <= maximum
    tree = build_topic_tree(markdown, COUNTER)
    plans = split_document(tree, {"0"}, markdown, COUNTER, SplitLimits(target, maximum))
    assert sum(block in part.markdown for part in plans) == 1
    assert "".join(part.markdown for part in plans) == markdown
    assert all(part.tokens <= maximum for part in plans)


def test_table_stays_whole_when_its_heading_would_push_it_over_maximum() -> None:
    heading = "# Data\n\n"
    table = "| A | B |\n| --- | --- |\n| x. y. | z |\n"
    maximum = COUNTER.count(table)
    markdown = heading + table
    assert COUNTER.count(markdown) > maximum
    spans = split_by_paragraphs(markdown, 0, len(markdown), COUNTER, SplitLimits(maximum, maximum))
    assert [markdown[left:right] for left, right in spans] == [heading, table]


def test_paragraph_group_is_split_when_exact_count_exceeds_target() -> None:
    counter = TokenCounter()
    first, second = "First.\n\n", "Second."
    markdown = first + second
    target = counter.count(first) + counter.count(second)
    measure = counter.count

    def count_with_extra_join_token(text: str) -> int:
        return target + 1 if text == markdown else measure(text)

    with patch.object(counter, "count", side_effect=count_with_extra_join_token):
        assert split_by_paragraphs(markdown, 0, len(markdown), counter, SplitLimits(target, target + 1)) == [
            (0, len(first)),
            (len(first), len(markdown)),
        ]


@pytest.mark.parametrize("prefix", ["", "# Parent\n\n## Selected\n\n"])
def test_image_is_not_orphaned_when_its_paragraph_is_too_large(prefix: str) -> None:
    marker = '::image{id="img_1"}'
    markdown = prefix + "text from the passage " * 18 + "\n\n" + marker + "\n\nAfter.\n"
    spans = split_by_paragraphs(markdown, 0, len(markdown), COUNTER, SplitLimits(15, 35))
    fragments = [markdown[start:end] for start, end in spans]
    with_marker = next(fragment for fragment in fragments if marker in fragment)
    assert with_marker.split(marker, 1)[0].strip()
    assert "".join(fragments) == markdown
    assert all(COUNTER.count(fragment) <= 35 for fragment in fragments)


def test_image_immediately_after_subsection_heading_stays_with_heading() -> None:
    marker = '::image{id="img_1"}'
    child = "## Selected\n\n" + marker + "\n\n" + "Text after the figure. " * 20
    markdown = "# Parent\n\n" + child
    tree = build_topic_tree(markdown, COUNTER)
    plans = split_document(tree, {"1.1"}, markdown, COUNTER, SplitLimits(20, 40))
    assert plans[0].markdown.startswith("## Selected\n\n" + marker)
    assert "".join(plan.markdown for plan in plans) == child


def test_oversized_paragraph_splits_at_sentences_and_keeps_sentence_above_target() -> None:
    first = "The first sentence contains a little information. "
    second = "The second sentence contains a little more information. "
    markdown = first + second
    maximum = max(COUNTER.count(first), COUNTER.count(second))
    spans = split_by_paragraphs(markdown, 0, len(markdown), COUNTER, SplitLimits(5, maximum))
    assert spans == [(0, len(first)), (len(first), len(markdown))]


def test_oversized_sentence_splits_on_tokens_without_damaging_unicode() -> None:
    markdown = "компонент объясняет состояние 👩🏽‍💻 и данные " * 90
    tree = build_topic_tree(markdown, COUNTER)
    plans = split_document(tree, {"0"}, markdown, COUNTER, SplitLimits(35, 50))
    assert len(plans) > 5
    assert all(COUNTER.count(part.markdown) == part.tokens <= 50 for part in plans)
    assert "\ufffd" not in "".join(part.markdown for part in plans)
    assert "".join(part.markdown for part in plans) == markdown


def test_maximum_that_cannot_hold_a_unicode_character() -> None:
    with pytest.raises(ValueError, match="Unicode"):
        split_by_paragraphs("👩", 0, 1, COUNTER, SplitLimits(1, 1))


def test_discontinuous_markdown_is_counted_with_its_separator() -> None:
    first = "a" * 101
    second = " ".join(["b"] * 15_454)
    markdown = first + "\nSkip this heading.\n" + second
    right = len(markdown) - len(second)
    left_tokens, right_tokens = COUNTER.count(first), COUNTER.count(second)
    maximum = left_tokens + right_tokens
    assert COUNTER.count(first + "\n\n" + second) > maximum
    roots = (
        TopicNode("1", "One", 1, 0, len(first), left_tokens, left_tokens),
        TopicNode("2", "Two", 1, right, len(markdown), right_tokens, right_tokens),
    )
    plans = split_document(roots, {"1", "2"}, markdown, COUNTER, SplitLimits(maximum, maximum))
    assert [plan.markdown for plan in plans] == [first, second]
    assert [plan.tokens for plan in plans] == [left_tokens, right_tokens]


def test_discontinuous_ranges_keep_one_blank_line_and_deduplicate_topic_ids() -> None:
    markdown = "first\n\nskipped\n\nlast\n\n"
    cut = markdown.index("last")
    roots = (
        TopicNode("1", "Title", 1, 0, len("first\n\n"), 1, 1),
        TopicNode("1", "Title", 1, cut, len(markdown), 1, 1),
    )
    [plan] = split_document(roots, {"1"}, markdown, COUNTER, DEFAULT_LIMITS)
    assert plan.markdown == "first\n\nlast"
    assert plan.topic_ids == ("1",)
    assert plan.tokens == COUNTER.count(plan.markdown)


def test_five_chapter_textbook_has_seven_to_ten_parts() -> None:
    paragraph = PARAGRAPH * 12 + "\n\n"
    markdown = "".join(
        f"# Chapter {chapter}\n\n" + "".join(f"## Section {section}\n\n" + paragraph * 20 for section in range(6))
        for chapter in range(1, 6)
    )
    tree = build_topic_tree(markdown, COUNTER)
    assert 115_000 < COUNTER.count(markdown) < 130_000
    plans = split_document(tree, {node.id for node in tree}, markdown, COUNTER, DEFAULT_LIMITS)
    assert 7 <= len(plans) <= 10
    assert all(part.markdown.startswith(("#", PARAGRAPH)) for part in plans)
    assert "".join(part.markdown for part in plans) == markdown


@pytest.mark.parametrize("repetitions", [2, 14], ids=["short-paragraphs", "long-paragraphs"])
def test_three_hundred_thousand_token_topic_splits_in_under_one_second(repetitions: int) -> None:
    paragraph = PARAGRAPH * repetitions + "\n\n"
    tokens_per_paragraph = COUNTER.count(paragraph * 100) / 100
    markdown = paragraph * round(300_000 / tokens_per_paragraph)
    tree = build_topic_tree(markdown, COUNTER)
    assert 295_000 < tree[0].total_tokens < 305_000
    started = perf_counter()
    plans = split_document(tree, {"0"}, markdown, COUNTER, DEFAULT_LIMITS)
    elapsed = perf_counter() - started
    assert elapsed < 1, f"{elapsed:.3f}s to split {tree[0].total_tokens} tokens"
    assert "".join(part.markdown for part in plans) == markdown
    assert all(part.tokens <= DEFAULT_LIMITS.maximum for part in plans)


@pytest.mark.parametrize("seed", range(200))
def test_random_trees_preserve_selected_ranges_and_count_final_markdown(seed: int) -> None:
    rng = Random(seed)
    markdown = "".join(
        f"# Chapter {chapter}\n\n"
        + PARAGRAPH * rng.randint(1, 4)
        + "\n\n"
        + "".join(
            f"## Section {section}\n\n" + PARAGRAPH * rng.randint(1, 8) + "\n\n" for section in range(rng.randint(0, 4))
        )
        for chapter in range(rng.randint(1, 5))
    )
    tree = build_topic_tree(markdown, COUNTER)
    nodes = [node for root in tree for node in (root, *root.children)]
    selected = {node.id for node in rng.sample(nodes, rng.randint(1, len(nodes)))}
    expected = sorted({position for node in nodes if node.id in selected for position in range(node.start, node.end)})
    limits = SplitLimits(65, 105)
    plans = split_document(tree, selected, markdown, COUNTER, limits)
    assert plans == split_document(tree, selected, markdown, COUNTER, limits)
    assert [position for plan in plans for start, end in plan.spans for position in range(start, end)] == expected
    assert all(part.tokens == COUNTER.count(part.markdown) <= limits.maximum for part in plans)
