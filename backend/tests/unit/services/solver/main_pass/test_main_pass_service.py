"""The main pass builds the cached layers, repairs violations and maps images."""

from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.core.settings.solver import SolverSettings
from src.app.services.solver.main_pass.directives import PageDraft
from src.app.services.solver.main_pass.main_pass import MainPassService
from src.app.services.solver.main_pass.prompts import MAIN_PASS_SYSTEM_PROMPT
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.llm.llm_client import FakeLLMClient
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fakes.repositories.widgets import FakePrimitiveRepository
from tests.support.fixtures.main_pass import (
    build_images,
    build_input,
    build_page_draft,
    build_primitives,
)

pytestmark = pytest.mark.unit


def _draft(name: str = "page_draft.json") -> PageDraft:
    return PageDraft.model_validate(build_page_draft(name))


async def _primitive_repo() -> FakePrimitiveRepository:
    repo = FakePrimitiveRepository()
    for primitive in build_primitives():
        await repo.upsert(
            primitive_id=primitive.id,
            version=primitive.version,
            description=primitive.description,
            modes=primitive.modes,
            params_schema=primitive.params_schema,
        )
    return repo


def _service(
    *,
    llm: FakeLLMClient,
    primitives: FakePrimitiveRepository,
    max_tokens: int = 1234,
    max_widgets: int = 4,
    metrics: RecordingMetricsCollector | None = None,
) -> MainPassService:
    return MainPassService(
        llm=llm,
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        primitives=lambda _: primitives,
        settings=SolverSettings(main_pass_max_tokens=max_tokens, max_widgets_per_part=max_widgets),
        metrics=metrics or RecordingMetricsCollector(),
    )


async def test_builds_two_cached_layers_and_one_volatile_message() -> None:
    primitives = await _primitive_repo()
    llm = FakeLLMClient(structured=[_draft()])
    service = _service(llm=llm, primitives=primitives, max_tokens=2048)
    payload = build_input()

    result = await service.run(payload)

    (request,) = llm.requests
    assert request.purpose == "main_pass"
    assert request.max_tokens == 2048
    assert request.metadata == {"document_id": str(payload.document_id), "part_id": str(payload.part_id)}
    assert [block.cache for block in request.system] == [True, True]

    catalog_block, document_block = (block.text for block in request.system)
    assert MAIN_PASS_SYSTEM_PROMPT in catalog_block
    assert "- At most 4 widget directives per part." in catalog_block
    for primitive in build_primitives():
        assert primitive.id in catalog_block
        assert ", ".join(primitive.modes) in catalog_block
    assert "level: novice" in document_block
    assert "<document_title>Neural networks</document_title>" in document_block
    assert "- From neurons to layers" in document_block
    assert "weighted sum" not in document_block

    (message,) = request.messages
    assert message.role == "user"
    assert isinstance(message.content, str)
    assert payload.part_title in message.content
    assert "weighted sum" in message.content
    assert 'alias="img_1"' in message.content
    assert "<part_topics>" in message.content

    assert result.draft.markdown.startswith("## From neurons to layers")
    assert result.draft.directives == (
        MainPassDirective(
            ref="w1",
            kind="widget",
            intent="Show how the weighted sum of three inputs becomes one neuron output.",
            primitive_hint="three-frame",
            mode_hint="steps",
            source_span="A neuron computes a weighted sum of its inputs",
        ),
        MainPassDirective(
            ref="img_1",
            kind="image",
            intent="The diagram of a single neuron with three inputs from the source part.",
            image_id="img_1",
            source_span="A neuron computes a weighted sum of its inputs",
        ),
        MainPassDirective(
            ref="q1",
            kind="quiz",
            intent="Check that the reader can tell a weight from an activation function.",
            source_span="A neuron computes a weighted sum of its inputs",
        ),
    )
    assert result.draft.key_terms == ("neuron", "weight", "bias", "activation function", "layer", "ReLU")


async def test_returns_spans_and_the_alias_to_image_id_mapping() -> None:
    primitives = await _primitive_repo()
    service = _service(llm=FakeLLMClient(structured=[_draft()]), primitives=primitives)

    result = await service.run(build_input())

    assert [span.ref for span in result.spans] == ["w1", "img_1", "q1"]
    source = build_input().part_markdown
    assert [source[span.start : span.end] for span in result.spans] == [
        "A neuron computes a weighted sum of its inputs",
    ] * 3
    image_ids = {image.alias: image.id for image in build_images("neurons")}
    assert result.image_ids == {"img_1": image_ids["img_1"]}
    assert isinstance(result.image_ids["img_1"], UUID)


async def test_two_parts_of_one_document_share_both_cached_blocks() -> None:
    primitives = await _primitive_repo()
    llm = FakeLLMClient(structured=[_draft(), _draft("page_draft_activation.json")])
    service = _service(llm=llm, primitives=primitives)
    first = build_input()
    second = build_input("activation")

    await service.run(first)
    await service.run(second)

    assert llm.requests[0].system == llm.requests[1].system
    assert llm.requests[0].messages != llm.requests[1].messages
    # The second part is not marked in the cached document block: only the
    # volatile message changes, so the provider can reuse the cache.
    assert "sigmoid" not in llm.requests[1].system[1].text


async def test_empty_catalog_still_produces_the_cached_layer() -> None:
    llm = FakeLLMClient(structured=[_draft()])
    service = _service(llm=llm, primitives=FakePrimitiveRepository())

    await service.run(build_input())

    assert "- none available" in llm.requests[0].system[0].text


async def test_logs_one_summary_line_with_output_counts(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="src.app.services.solver.main_pass.main_pass")
    primitives = await _primitive_repo()
    service = _service(llm=FakeLLMClient(structured=[_draft()]), primitives=primitives)

    await service.run(build_input())

    (record,) = [record for record in caplog.records if record.message == "Main pass completed."]
    assert record.__dict__["directives"] == 3
    assert record.__dict__["key_terms"] == 6
    assert record.__dict__["markdown_chars"] > 0
    assert record.__dict__["retried"] is False


async def test_a_first_answer_violation_is_sent_back_for_one_repair_turn() -> None:
    primitives = await _primitive_repo()
    metrics = RecordingMetricsCollector()
    llm = FakeLLMClient(structured=[_draft("page_draft_conflict.json"), _draft()])
    service = _service(llm=llm, primitives=primitives, metrics=metrics)

    result = await service.run(build_input())

    assert len(llm.requests) == 2
    retry_message = llm.requests[1].messages[-1]
    assert retry_message.role == "user"
    assert isinstance(retry_message.content, str)
    assert "The previous draft breaks these rules" in retry_message.content
    assert "identical primitive and mode" in retry_message.content
    assert "do not alter markdown to match key_terms" in retry_message.content
    assert llm.requests[1].messages[-2].role == "assistant"

    assert [directive.mode_hint for directive in result.draft.directives] == ["steps", None, None]
    first_answer = metrics.counters_named("main_pass.draft_violations_total")
    assert [(counter.labels["attempt"], counter.by) for counter in first_answer] == [("first", 1)]


async def test_a_violation_surviving_the_retry_is_sanitized(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("WARNING", logger="src.app.services.solver.main_pass.main_pass")
    primitives = await _primitive_repo()
    metrics = RecordingMetricsCollector()
    llm = FakeLLMClient(
        structured=[
            _draft("page_draft_conflict.json"),
            _draft("page_draft_conflict.json"),
        ]
    )
    service = _service(llm=llm, primitives=primitives, metrics=metrics)

    result = await service.run(build_input())

    # The second widget keeps its primitive but loses the mode: the resolver
    # picks a different mode instead of repeating the same widget twice.
    assert [directive.mode_hint for directive in result.draft.directives] == ["steps", None, None]
    assert '::widget{ref="w2"}' in result.draft.markdown

    violations = metrics.counters_named("main_pass.draft_violations_total")
    assert [(counter.labels["attempt"], counter.by) for counter in violations] == [("first", 1), ("retry", 1)]
    warnings = [record for record in caplog.records if record.message == "Main pass rule violation."]
    assert [warning.__dict__["attempt"] for warning in warnings] == ["first", "retry"]


async def test_a_clean_first_answer_logs_no_violation() -> None:
    primitives = await _primitive_repo()
    metrics = RecordingMetricsCollector()
    service = _service(llm=FakeLLMClient(structured=[_draft()]), primitives=primitives, metrics=metrics)

    await service.run(build_input())

    assert metrics.counters_named("main_pass.draft_violations_total") == []


async def test_the_widget_limit_comes_from_the_settings() -> None:
    primitives = await _primitive_repo()
    service = _service(
        llm=FakeLLMClient(structured=[_draft(), _draft()]),
        primitives=primitives,
        max_widgets=0,
    )

    result = await service.run(build_input())

    assert [directive.ref for directive in result.draft.directives] == ["img_1", "q1"]
    assert "::widget" not in result.draft.markdown


async def test_final_directives_follow_page_order_without_retry() -> None:
    first = _draft()
    reversed_draft = first.model_copy(update={"directives": list(reversed(first.directives))})
    llm = FakeLLMClient(structured=[reversed_draft])
    result = await _service(llm=llm, primitives=await _primitive_repo()).run(build_input())
    assert [item.ref for item in result.draft.directives] == [item.ref for item in first.directives]
    assert len(llm.requests) == 1


async def test_unrepairable_terms_raise_instead_of_returning_invalid_draft() -> None:
    broken = _draft().model_copy(update={"key_terms": ["missing"] * 5})
    llm = FakeLLMClient(structured=[broken, broken])
    with pytest.raises(ValueError, match="cannot preserve the output schema"):
        await _service(llm=llm, primitives=await _primitive_repo()).run(build_input())


async def test_inline_cleanup_does_not_create_a_dangling_marker() -> None:
    text = "body " * 50 + '\n:widget[label]::widget{ref="w1"}'
    broken = PageDraft(markdown=text, directives=[], key_terms=["body"] * 5)
    llm = FakeLLMClient(structured=[broken, broken])
    result = await _service(llm=llm, primitives=await _primitive_repo()).run(build_input())
    assert result.draft.directives == ()
    from src.app.services.solver.main_pass.directive_parser import extract_markers

    assert extract_markers(result.draft.markdown) == ([], [])


@pytest.mark.parametrize("spaces", [" ", "  ", "\t", "   "])
async def test_inline_cleanup_cannot_expose_indented_marker(spaces: str) -> None:
    text = "body " * 50 + f'\n:widget[label]{spaces}::widget{{ref="w1"}}'
    broken = PageDraft(markdown=text, directives=[], key_terms=["body"] * 5)
    llm = FakeLLMClient(structured=[broken, broken])
    result = await _service(llm=llm, primitives=await _primitive_repo()).run(build_input())
    assert len(llm.requests) == 2
    assert result.draft.directives == ()
    assert "body " * 50 in result.draft.markdown
    from src.app.services.solver.main_pass.directive_parser import extract_markers

    assert extract_markers(result.draft.markdown) == ([], [])


async def test_list_directive_repaired_and_tab_code_preserved() -> None:
    text = "body " * 50 + '\n\n100. Example\n\n     ::quiz{ref="q1"}\n\nAfter list.\n\n\t::widget{ref="w1"}'
    broken = PageDraft(markdown=text, directives=[], key_terms=["body"] * 5)
    llm = FakeLLMClient(structured=[broken, broken])
    result = await _service(llm=llm, primitives=await _primitive_repo()).run(build_input())
    assert len(llm.requests) == 2
    assert '::quiz{ref="q1"}' not in result.draft.markdown
    assert '\t::widget{ref="w1"}' in result.draft.markdown
    assert result.draft.directives == ()


async def test_tab_indented_code_does_not_trigger_retry() -> None:
    text = "body " * 50 + '\n\n\t::widget{ref="w1"}'
    draft = PageDraft(markdown=text, directives=[], key_terms=["body"] * 5)
    llm = FakeLLMClient(structured=[draft])
    result = await _service(llm=llm, primitives=await _primitive_repo()).run(build_input())
    assert len(llm.requests) == 1
    assert result.draft.markdown == text
    assert result.draft.directives == ()


@pytest.mark.parametrize(
    ("fragment", "expected_code"),
    [
        ('- - ::quiz{ref="q1"}', None),
        ('::quiz{ref="q1"}\n    ::widget{ref="w1"}', '    ::widget{ref="w1"}'),
    ],
)
async def test_nested_directive_repair_preserves_adjacent_code(fragment: str, expected_code: str | None) -> None:
    text = "body " * 50 + "\n\n" + fragment
    draft = PageDraft(markdown=text, directives=[], key_terms=["body"] * 5)
    llm = FakeLLMClient(structured=[draft, draft])
    result = await _service(llm=llm, primitives=await _primitive_repo()).run(build_input())
    assert len(llm.requests) == 2
    assert result.draft.directives == ()
    assert '::quiz{ref="q1"}' not in result.draft.markdown
    if expected_code is not None:
        assert expected_code in result.draft.markdown
