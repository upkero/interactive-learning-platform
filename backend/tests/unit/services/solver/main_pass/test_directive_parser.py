"""Syntax and recovery of directive slots in a main-pass draft."""

import pytest

from src.app.services.solver.main_pass.directive_parser import check_draft, extract_markers, sanitize_draft
from src.app.services.solver.main_pass.directives import Directive, PageDraft

pytestmark = pytest.mark.unit


def entry(ref: str, kind: str = "widget", **extra: object) -> Directive:
    data: dict[str, object] = {
        "ref": ref,
        "kind": kind,
        "intent": "Explain this concept to the reader",
        "source_span": "A source quotation",
        **extra,
    }
    if kind == "image":
        data["image_id"] = ref
    return Directive.model_validate(data)


def draft(markdown: str, directives: list[Directive], key_terms: list[str] | None = None) -> PageDraft:
    return PageDraft(
        markdown=markdown + "\n" + "filler " * 40, directives=directives, key_terms=key_terms or ["filler"] * 5
    )


def test_leaf_syntax_offsets_and_image_id() -> None:
    text = 'Intro\r\n::widget{ref="w1"}\r\n::image{id="img_1"}\r\n::quiz{ref="q1"}\r\n'
    markers, issues = extract_markers(text)
    assert issues == []
    assert [(m.ref, m.kind) for m in markers] == [("w1", "widget"), ("img_1", "image"), ("q1", "quiz")]
    assert text[markers[0].start : markers[0].end] == '::widget{ref="w1"}'
    assert markers[0].line == 2


def test_fences_and_plain_colon_text() -> None:
    text = '   ````md\n```\n::widget{ref="w1"}\n````\n~~~\n::quiz{ref="q1"}\n~~~\n::before text\n::image{id="img_1"}'
    markers, issues = extract_markers(text)
    assert issues == []
    assert [(m.ref, m.kind) for m in markers] == [("img_1", "image")]


@pytest.mark.parametrize(
    "text",
    [
        '   ::widget{ref="w1"}',
        '- item\n  ::quiz{ref="q1"}',
        ':::widget{ref="w1"}',
        '::widget ref="w1"',
        '::widget{ref="w1" mode_hint="steps"}',
        '::image{ref="img_1"}',
        "text :widget[hello]",
    ],
)
def test_unsupported_syntax_is_reported(text: str) -> None:
    markers, issues = extract_markers(text)
    assert markers == []
    assert issues


def test_all_syntax_errors_collected() -> None:
    _, issues = extract_markers('::widget ref="w1"\n::quiz{ref="q1" extra="x"}\n')
    assert len(issues) == 2


def test_check_reports_each_structural_problem() -> None:
    text = "\n".join(
        [
            '::widget{ref="w1"}',
            '::widget{ref="w1"}',
            '::quiz{ref="w2"}',
            '::image{id="img_2"}',
            '::image{id="img_2"}',
            '::quiz{ref="q2"}',
        ]
    )
    items = [entry("w1"), entry("w1"), entry("w2"), entry("q1", "quiz"), entry("img_2", "image")]
    issues = check_draft(text, items, image_aliases={"img_1"}, max_widgets=1, max_quizzes=1)
    for fragment in (
        "duplicate directive ref",
        "appears more than once",
        "different kinds",
        "unknown image",
        "used more than once",
        "missing from the markdown",
        "has no entry",
        "too many widget",
        "too many quiz",
    ):
        assert any(fragment in issue for issue in issues), (fragment, issues)


def test_alternation_uses_widget_sequence_and_both_hints() -> None:
    text = '::widget{ref="w1"}\nParagraph.\n::quiz{ref="q1"}\n::widget{ref="w2"}'
    first = entry("w1", primitive_hint="graph", mode_hint="watch")
    second = entry("w2", primitive_hint="graph", mode_hint="watch")
    items = [first, entry("q1", "quiz"), second]
    assert any("identical primitive and mode" in x for x in check_draft(text, items, alternation=True))
    for replacement in (entry("w2", mode_hint="watch"), entry("w2", primitive_hint="tree", mode_hint="watch")):
        assert check_draft(text, [first, items[1], replacement], alternation=True) == []
    cleaned = sanitize_draft(draft(text, items), max_widgets=6)
    assert cleaned.directives[-1].mode_hint is None
    assert sanitize_draft(cleaned, max_widgets=6) == cleaned


def test_sanitize_removes_dangling_duplicates_unknown_and_excess() -> None:
    text = "\n".join(
        [
            '::widget{ref="w1"}',
            '::widget{ref="w1"}',
            '::widget{ref="w2"}',
            '::quiz{ref="q1"}',
            '::quiz{ref="q2"}',
            '::image{id="img_1"}',
            '::image{id="img_1"}',
            '::image{id="img_2"}',
            '::quiz{ref="q9"}',
            '  ::widget{ref="w8"}',
            "inline :quiz[invalid]",
        ]
    )
    items = [
        entry("w1"),
        entry("w1"),
        entry("w2"),
        entry("w3"),
        entry("q1", "quiz"),
        entry("q2", "quiz"),
        entry("img_1", "image"),
        entry("img_2", "image"),
    ]
    cleaned = sanitize_draft(draft(text, items), max_widgets=1, max_quizzes=1, image_aliases={"img_1"})
    assert [x.ref for x in cleaned.directives] == ["w1", "q1", "img_1"]
    assert cleaned.markdown.count('::image{id="img_1"}') == 1
    assert (
        check_draft(
            cleaned.markdown,
            cleaned.directives,
            max_widgets=1,
            max_quizzes=1,
            image_aliases={"img_1"},
            alternation=True,
            key_terms=cleaned.key_terms,
        )
        == []
    )
    assert sanitize_draft(cleaned, max_widgets=1, max_quizzes=1, image_aliases={"img_1"}) == cleaned


def test_empty_after_sanitizing_does_not_throw() -> None:
    broken = PageDraft.model_construct(markdown='::widget{ref="w1"}', directives=[], key_terms=["missing"])
    cleaned = sanitize_draft(broken, max_widgets=0)
    assert cleaned.markdown == ""
    assert cleaned.directives == []
    assert cleaned.key_terms == []


def test_blockquote_directives_are_reported_and_removed() -> None:
    text = '> ::widget{ref="w1"}\n> > ::quiz{ref="q1"}'
    assert len(extract_markers(text)[1]) == 2
    cleaned = sanitize_draft(draft(text, []), max_widgets=6)
    assert "::widget" not in cleaned.markdown
    assert "::quiz" not in cleaned.markdown


def test_inline_code_and_quoted_fenced_code_are_preserved() -> None:
    text = 'Use `:widget[demo]` or ``:quiz[x]`` as examples.\n> ```\n> ::widget{ref="w1"}\n> ```'
    assert extract_markers(text) == ([], [])
    cleaned = sanitize_draft(draft(text, []), max_widgets=6)
    assert text in cleaned.markdown


def test_sanitize_inline_preserves_surrounding_prose_and_newlines() -> None:
    text = 'First :widget[bad]{ref="w9"} and `:quiz[example]` remain.\nSecond :quiz[bad]\nThird line.'
    cleaned = sanitize_draft(draft(text, []), max_widgets=6)
    assert "First  and `:quiz[example]` remain.\nSecond \nThird line." in cleaned.markdown
    assert extract_markers(cleaned.markdown)[1] == []


def test_escaped_inline_directive_is_plain_text() -> None:
    assert extract_markers(r"Text \:widget[example]")[1] == []


def test_quote_fence_cannot_close_plain_fenced_code() -> None:
    text = '```\n> ```\n::widget{ref="w1"}\n```\n'
    assert extract_markers(text) == ([], [])
    assert text in sanitize_draft(draft(text, []), max_widgets=6).markdown


def test_quoted_fence_stays_open_for_deeper_quote_and_ends_with_container() -> None:
    text = '> ```\n> > ```\n> ::widget{ref="w1"}\n> ```\n::quiz{ref="q1"}'
    markers, issues = extract_markers(text)
    assert issues == []
    assert [(marker.ref, marker.kind) for marker in markers] == [("q1", "quiz")]
    source = draft(text, [entry("q1", "quiz")])
    assert text in sanitize_draft(source, max_widgets=6).markdown


def test_unclosed_quoted_fence_ends_when_leaving_quote() -> None:
    text = '> ```\n> ::widget{ref="w1"}\n::quiz{ref="q1"}'
    markers, issues = extract_markers(text)
    assert issues == []
    assert [marker.ref for marker in markers] == ["q1"]
