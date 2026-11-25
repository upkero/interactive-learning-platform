import re
from itertools import pairwise
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import pytest

from src.app.contracts.llm.llm_request import LLMRequest
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
