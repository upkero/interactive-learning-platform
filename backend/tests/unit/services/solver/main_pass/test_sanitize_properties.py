"""Property tests for recovery of arbitrary directive combinations."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.app.services.solver.main_pass.directive_parser import check_draft, sanitize_draft
from src.app.services.solver.main_pass.directives import Directive, PageDraft

pytestmark = pytest.mark.unit


@st.composite
def draft_cases(draw: st.DrawFn) -> tuple[PageDraft, set[str], int, int]:
    references = [(f"w{i}", "widget") for i in range(1, 7)]
    references += [(f"q{i}", "quiz") for i in range(1, 7)]
    references += [(f"img_{i}", "image") for i in range(1, 7)]
    list_refs = draw(st.lists(st.sampled_from(references), max_size=24))
    marker_refs = draw(st.lists(st.sampled_from(references), max_size=35))
    directives: list[Directive] = []
    for ref, kind in list_refs:
        data: dict[str, object] = {
            "ref": ref,
            "kind": kind,
            "intent": "Explain this concept to the reader",
            "source_span": "A source quotation",
        }
        if kind == "widget":
            data["primitive_hint"] = draw(st.sampled_from([None, "graph", "array"]))
            data["mode_hint"] = draw(st.sampled_from([None, "watch", "steps"]))
        if kind == "image":
            data["image_id"] = ref
        directives.append(Directive.model_validate(data))
    lines = [f'::{kind}{{{"id" if kind == "image" else "ref"}="{ref}"}}' for ref, kind in marker_refs]
    malformed = draw(
        st.lists(
            st.sampled_from(
                [
                    '  ::quiz{ref="q1"}',
                    ':::widget{ref="w1"}',
                    '::image{id="img_1" extra="x"}',
                    "text :quiz[content]",
                    ' :widget[label]::widget{ref="w1"}',
                ]
            ),
            max_size=4,
        )
    )
    markdown = "\n".join(["filler " * 40, *lines, *malformed])
    aliases = set(draw(st.lists(st.sampled_from([f"img_{i}" for i in range(1, 7)]), unique=True)))
    return (
        PageDraft(markdown=markdown, directives=directives, key_terms=["filler"] * 5),
        aliases,
        draw(st.integers(0, 6)),
        draw(st.integers(0, 5)),
    )


@given(draft_cases())
@settings(max_examples=150, deadline=None)
def test_sanitizer_invariants(case: tuple[PageDraft, set[str], int, int]) -> None:
    draft, aliases, widgets, quizzes = case
    cleaned = sanitize_draft(draft, image_aliases=aliases, max_widgets=widgets, max_quizzes=quizzes)
    assert (
        check_draft(
            cleaned.markdown,
            cleaned.directives,
            image_aliases=aliases,
            max_widgets=widgets,
            max_quizzes=quizzes,
            alternation=True,
            key_terms=cleaned.key_terms,
        )
        == []
    )
    assert PageDraft.model_validate(cleaned.model_dump()) == cleaned
    assert sanitize_draft(cleaned, image_aliases=aliases, max_widgets=widgets, max_quizzes=quizzes) == cleaned
