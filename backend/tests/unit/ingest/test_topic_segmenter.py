import re
from itertools import pairwise
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

from src.app.contracts.llm.llm_request import LLMRequest
from src.app.ingest.markdown_syntax import parse_markdown
from src.app.ingest.parsers.markdown_parser import MarkdownParser
from src.app.ingest.tokens import TokenCounter
from src.app.ingest.topic_tree import build_topic_tree
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.services.documents.topic_segmenter import Section, Sections, TopicSegmenter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_segmenter_inserts_ordered_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    call = AsyncMock(
        return_value=Sections(
            sections=[Section(title="First", first_paragraph=1), Section(title="Second", first_paragraph=3)]
        )
    )
    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", call)
    segmenter = TopicSegmenter(cast(LLMClient, object()), counter=TokenCounter(), max_tokens=1000)
    result = await segmenter.segment("One.\n\nTwo.\n\nThree.")
    assert result == "## First\n\nOne.\n\nTwo.\n\n## Second\n\nThree.\n"
    assert call.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_segmenter_rejects_unordered_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    call = AsyncMock(
        return_value=Sections(
            sections=[Section(title="Second", first_paragraph=2), Section(title="First", first_paragraph=1)]
        )
    )
    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", call)
    segmenter = TopicSegmenter(cast(LLMClient, object()), counter=TokenCounter(), max_tokens=1000)
    with pytest.raises(ValueError, match="non-monotonic"):
        await segmenter.segment("One.\n\nTwo.")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_long_document_uses_overlapping_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    windows: list[list[int]] = []

    async def fake_call(llm: object, request: LLMRequest, schema: object) -> Sections:
        content = request.messages[0].content
        assert isinstance(content, str)
        numbers = [int(item) for item in re.findall(r"\[p(\d+)\]", content)]
        windows.append(numbers)
        return Sections(
            sections=[Section(title=f"Topic {n}", first_paragraph=n) for n in numbers if n == 1 or n % 5 == 0]
        )

    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", fake_call)
    counter = TokenCounter()
    segmenter = TopicSegmenter(cast(LLMClient, object()), counter=counter, max_tokens=12000)
    markdown = (Path(__file__).parents[2] / "fixtures/documents/long_no_headings.md").read_text(encoding="utf-8")
    result = await segmenter.segment(markdown)
    assert counter.count(markdown) > 40000
    assert len(windows) >= 3
    assert all(previous[-1] == current[0] for previous, current in pairwise(windows))
    assert result.count("## Topic") >= 3
    assert all(node.total_tokens <= 12000 for node in build_topic_tree(result, counter))


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("headed", [False, True])
async def test_single_40k_block_respects_model_budget_and_topic_limit(
    monkeypatch: pytest.MonkeyPatch, headed: bool
) -> None:
    counter = TokenCounter()
    maximum = 12000
    original = "word " * 45000
    source = ("# Existing\n\n" if headed else "") + original
    assert counter.count(source) > 40000
    seen: list[int] = []

    async def suggest(llm: object, request: LLMRequest, schema: object) -> Sections:
        content = request.messages[0].content
        assert isinstance(content, str)
        seen.append(counter.count(content))
        numbers = [int(value) for value in re.findall(r"\[p(\d+)\]", content)]
        return Sections(sections=[Section(title="Suggested", first_paragraph=numbers[0])])

    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", suggest)
    result = await TopicSegmenter(object(), counter=counter, max_tokens=maximum).segment(source)  # type: ignore[arg-type]
    assert seen and max(seen) <= 20000
    assert all(node.total_tokens <= maximum for node in build_topic_tree(result, counter))
    assert result.count("word ") == 45000
    if headed:
        assert result.startswith("# Existing\n\n")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_segmenter_never_inserts_heading_inside_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    async def suggest(llm: object, request: LLMRequest, schema: object) -> Sections:
        return Sections(
            sections=[Section(title="First", first_paragraph=1), Section(title="Second", first_paragraph=2)]
        )

    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", suggest)
    source = "````\n```\n# Example\n```\n````\n\nText."
    result = await TopicSegmenter(object(), counter=TokenCounter(), max_tokens=1000).segment(source)  # type: ignore[arg-type]
    assert "````\n```\n# Example\n```\n````" in result
    assert "## Second" in result
    assert [node.title for node in build_topic_tree(result, TokenCounter())] == ["First", "Second"]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "block"),
    [
        ("table_open", "Col A | Col B\n--- | ---\n" + "a | b\n" * 3200),
        ("code_block", "    " + "print(value) " * 3500 + "\n"),
    ],
    ids=["table", "indented-code"],
)
async def test_working_token_limit_keeps_large_table_and_indented_code_intact(
    monkeypatch: pytest.MonkeyPatch, kind: str, block: str
) -> None:
    counter = TokenCounter()
    assert 11000 < counter.count(block) < 20000
    call = AsyncMock(
        return_value=Sections(
            sections=[
                Section(title="Before", first_paragraph=1),
                Section(title="Block", first_paragraph=2),
                Section(title="After", first_paragraph=3),
            ]
        )
    )
    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", call)
    source = f"Intro text.\n\n{block}\nEnd text.\n"
    result = await TopicSegmenter(cast(LLMClient, object()), counter=counter).segment(source)
    assert "## After" in result
    before = [source[item.start : item.end] for item in parse_markdown(source).blocks if item.kind == kind]
    after = [result[item.start : item.end] for item in parse_markdown(result).blocks if item.kind == kind]
    assert before == after == [block]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["table", "code"])
async def test_oversized_indivisible_block_in_middle_skips_model(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    call = AsyncMock(return_value=Sections(sections=[]))
    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", call)
    counter = TokenCounter()
    large_block = "Col A | Col B\n--- | ---\n" + "a | b\n" * 6000
    if kind == "code":
        large_block = "    " + "print(value) " * 5500 + "\n"
    assert counter.count(large_block) > 20000
    source = f"Introduction.\n\nAnother paragraph.\n\n{large_block}\nConclusion.\n"
    with pytest.raises(ValueError, match="exceeds the model window"):
        await TopicSegmenter(AsyncMock(spec=LLMClient), counter=counter).segment(source)
    call.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("with_source_spans", [False, True])
async def test_long_paragraph_with_images_fits_windows_and_preserves_ownership(
    monkeypatch: pytest.MonkeyPatch, with_source_spans: bool
) -> None:
    counter = TokenCounter()
    windows: list[list[int]] = []

    async def suggest(llm: LLMClient, request: LLMRequest, schema: type[Sections]) -> Sections:
        content = request.messages[0].content
        assert isinstance(content, str)
        assert counter.count(content) <= 20000
        numbers = [int(value) for value in re.findall(r"\[p(\d+)\]", content)]
        windows.append(numbers)
        return Sections(sections=[Section(title=f"Topic {n}", first_paragraph=n) for n in numbers])

    monkeypatch.setattr("src.app.services.documents.topic_segmenter.call_structured", suggest)
    source = (
        "Opening notes.\n\nSecond paragraph.\n\n"
        "Start ![early figure](data:image/png;base64,AAAA) "
        + "word " * 30000
        + "End ![late figure](data:image/png;base64,AAAA).\n\nConclusion.\n"
    )
    parsed = MarkdownParser().parse(source.encode(), filename="long.md")
    spans = (
        {image.ref: image.paragraph_span for image in parsed.images if image.paragraph_span is not None}
        if with_source_spans
        else None
    )
    assert counter.count(parsed.markdown) > 40000
    result = await TopicSegmenter(AsyncMock(spec=LLMClient), counter=counter).segment(
        parsed.markdown, image_spans=spans
    )
    assert len(windows) > 1
    assert all(previous[-1] == current[0] for previous, current in pairwise(windows))
    assert result.count("word ") == 30000
    topics = build_topic_tree(result, counter)
    assert len(topics) > 3 and all(topic.total_tokens <= 22000 for topic in topics)
    early = next(topic for topic in topics if "img_1" in topic.image_ids)
    late = next(topic for topic in topics if "img_2" in topic.image_ids)
    assert "late figure" in result[late.start : late.end]
    if with_source_spans:
        assert "early figure" in result[early.start : early.end]
        assert early.id != late.id
    else:
        assert early.id == late.id
