"""Syntax and recovery of directive slots in a main-pass draft."""

from pathlib import Path

import pytest
from markdown_it import MarkdownIt

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


def test_empty_after_sanitizing_cannot_be_published() -> None:
    broken = PageDraft.model_construct(markdown='::widget{ref="w1"}', directives=[], key_terms=["missing"])
    with pytest.raises(ValueError, match="cannot preserve the output schema"):
        sanitize_draft(broken, max_widgets=0)


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


def test_indented_code_and_inline_attribute_directive() -> None:
    text = 'Paragraph.\n\n    ::widget{ref="w1"}\n\nExample :widget{ref="w1"} here.'
    markers, issues = extract_markers(text)
    assert markers == []
    assert len(issues) == 1 and "inline" in issues[0]


def test_ordered_list_indentation_is_not_code() -> None:
    text = 'Paragraph.\n\n100. Example\n\n     ::quiz{ref="q1"}'
    markers, issues = extract_markers(text)
    assert markers == []
    assert len(issues) == 1
    cleaned = sanitize_draft(draft(text, []), max_widgets=6)
    assert "100. Example" in cleaned.markdown
    assert '::quiz{ref="q1"}' not in cleaned.markdown
    assert extract_markers(cleaned.markdown) == ([], [])


def test_tab_indented_code_is_preserved() -> None:
    text = 'Paragraph.\n\n\t::widget{ref="w1"}'
    assert extract_markers(text) == ([], [])
    assert text in sanitize_draft(draft(text, []), max_widgets=6).markdown


def test_nested_list_directive_is_reported_and_removed() -> None:
    text = 'Paragraph.\n\n- - ::quiz{ref="q1"}'
    assert extract_markers(text)[0] == []
    assert len(extract_markers(text)[1]) == 1
    cleaned = sanitize_draft(draft(text, []), max_widgets=6)
    assert '::quiz{ref="q1"}' not in cleaned.markdown
    assert extract_markers(cleaned.markdown) == ([], [])


def test_code_immediately_after_leaf_directive_is_preserved() -> None:
    text = 'Paragraph.\n\n::quiz{ref="q1"}\n    ::widget{ref="w1"}'
    markers, issues = extract_markers(text)
    assert [marker.ref for marker in markers] == ["q1"]
    assert issues == []
    cleaned = sanitize_draft(draft(text, []), max_widgets=6)
    assert '::quiz{ref="q1"}' not in cleaned.markdown
    assert '    ::widget{ref="w1"}' in cleaned.markdown
    assert extract_markers(cleaned.markdown) == ([], [])


def test_attribute_free_leaf_still_delimits_following_code() -> None:
    text = 'Paragraph.\n\n::quiz\n    ::widget{ref="w1"}'
    markers, issues = extract_markers(text)
    assert markers == []
    assert len(issues) == 1
    cleaned = sanitize_draft(draft(text, []), max_widgets=6)
    assert '    ::widget{ref="w1"}' in cleaned.markdown
    assert extract_markers(cleaned.markdown) == ([], [])


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85", "\x0b", "\x0c"])
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_unicode_separators_preserve_code_and_source_offsets(separator: str, newline: str) -> None:
    code = newline.join(["```", '::widget{ref="w1"}', "```"])
    source = separator.join(["A", "B", "C"]) + newline * 2 + code + newline + '::quiz{ref="q1"}'
    markers, issues = extract_markers(source)
    assert issues == []
    assert [marker.ref for marker in markers] == ["q1"]
    marker = markers[0]
    assert marker.line == 6
    assert source[marker.start : marker.end] == '::quiz{ref="q1"}'
    cleaned = sanitize_draft(draft(source, [entry("q1", "quiz")]), max_widgets=6)
    assert code in cleaned.markdown
    assert extract_markers(cleaned.markdown)[1] == []


def test_removing_cr_terminated_directive_keeps_following_marker() -> None:
    source = 'intro\r::widget{ref="w1"}\r::quiz{ref="q1"}\r'
    cleaned = sanitize_draft(draft(source, [entry("q1", "quiz")]), max_widgets=6)
    assert '::widget{ref="w1"}' not in cleaned.markdown
    assert '::quiz{ref="q1"}' in cleaned.markdown
    assert [marker.ref for marker in extract_markers(cleaned.markdown)[0]] == ["q1"]


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85", "\x0b", "\x0c"])
def test_unicode_separator_is_not_indentation_or_line_break(separator: str) -> None:
    text = separator + '::widget{ref="w1"}'
    assert extract_markers(text) == ([], [])
    assert text in sanitize_draft(draft(text, []), max_widgets=6).markdown


@pytest.mark.parametrize(
    "example",
    [
        "Use `:widget[one]\n:quiz[two]\n:widget[three]` here.",
        "Use ``a `tick\n:widget[label]\nend`` here.",
        "> Use ``\n> :quiz[x]\n> `` in a quote.",
        "- Use `\n  :widget[label]\n  ` in a list.",
        "Heading `\n:widget[label]\nclose`\n===",
        "Use `\n  ::quiz not a block\nclose` here.",
    ],
)
def test_commonmark_inline_code_masks_only_its_source_spans(example: str) -> None:
    text = example + "\n\nOther text :quiz[outside]"
    assert len(extract_markers(text)[1]) == 1
    assert sanitize_draft(draft(text, []), max_widgets=6).markdown.startswith(example + "\n\nOther text \n")


@pytest.mark.parametrize(
    "example",
    [r"Escaped \`", "An unmatched `` opener", "Use ` then a different closing run ``"],
)
def test_non_code_backticks_do_not_hide_inline_directives(example: str) -> None:
    text = example + "\n:widget[label]"
    assert len(extract_markers(text)[1]) == 1
    cleaned = sanitize_draft(draft(text, []), max_widgets=6)
    assert cleaned.markdown.startswith(example + "\n&#32;\n")
    assert [token.type for token in MarkdownIt().parse(cleaned.markdown)] == [
        "paragraph_open",
        "inline",
        "paragraph_close",
    ]


_SHARED_MARKDOWN = Path(__file__).resolve().parents[4] / "support" / "fixtures" / "main_pass" / "directives.md"


@pytest.mark.parametrize(
    ("name", "markers", "issues", "code"),
    [
        ("leaf-before-code", ["w1"], 0, [":quiz[example]\n"]),
        ("quote-list-before-code", [], 1, [":widget[example]\n"]),
        ("multiline-inline-code", [], 1, []),
        ("wide-container", [], 2, [":widget[example]\n"]),
        ("nested-containers", [], 4, []),
        ("unclosed-container", [], 1, []),
    ],
)
def test_shared_directive_fixtures(name: str, markers: list[str], issues: int, code: list[str]) -> None:
    fixture = _SHARED_MARKDOWN.read_text(encoding="utf-8")
    source = fixture.split(f"<!-- case: {name} -->\n", 1)[1].split("\n<!-- case: ", 1)[0].strip("\n")
    found, violations = extract_markers(source)
    assert [marker.ref for marker in found] == markers
    assert len(violations) == issues
    cleaned = sanitize_draft(draft(source, []), max_widgets=6)
    assert extract_markers(cleaned.markdown) == ([], [])
    assert [token.content for token in MarkdownIt().parse(cleaned.markdown) if token.type == "code_block"] == code


@pytest.mark.parametrize(("name", "count"), [("inline-syntax", 2), ("preserved-urls", 1), ("unquoted-brace", 1)])
def test_shared_inline_cleanup(name: str, count: int) -> None:
    fixture = _SHARED_MARKDOWN.read_text(encoding="utf-8")
    section = fixture.split(f"<!-- case: {name} -->\n", 1)[1].split("\n<!-- case: ", 1)[0].strip("\n")
    source, expected = section.split("\n<!-- cleaned -->\n")
    assert len(extract_markers(source)[1]) == count
    assert sanitize_draft(draft(source, []), max_widgets=6).markdown == expected + "\n" + "filler " * 40
    assert extract_markers(expected) == ([], [])


def test_shared_fence_cleanup_retains_the_valid_leaf() -> None:
    fixture = _SHARED_MARKDOWN.read_text(encoding="utf-8")
    section = fixture.split("<!-- case: exposed-fence -->\n", 1)[1].split("\n<!-- case: ", 1)[0].strip("\n")
    source, expected = section.split("\n<!-- cleaned -->\n")
    cleaned = sanitize_draft(draft(source, [entry("w1")]), max_widgets=6)
    assert cleaned.markdown == expected + "\n" + "filler " * 40
    found, issues = extract_markers(cleaned.markdown)
    assert [marker.ref for marker in found] == ["w1"]
    assert not issues


@pytest.mark.parametrize(
    ("attribute", "remainder"),
    [
        ("{title={a}", ""),
        ("{title=a{b{c}", ""),
        ('{title="one" other="two"}', ""),
        ('{title="one"other="two"}', '{title="one"other="two"}'),
    ],
)
def test_inline_attributes_preserve_malformed_suffixes(attribute: str, remainder: str) -> None:
    original = f"See :quiz[label]{attribute} and continue."
    cleaned = sanitize_draft(draft(original, []), max_widgets=6)
    assert cleaned.markdown.startswith(f"See {remainder} and continue.\n")


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_inline_attribute_spans_inside_a_quote(newline: str) -> None:
    source = newline.join(["> Keep :quiz[one", "> two]{", "> title='a } b' .help", "> } and this."])
    cleaned = sanitize_draft(draft(source, []), max_widgets=6)
    assert cleaned.markdown.startswith("> Keep  and this.\n")


def test_inline_syntax_ignores_escapes_and_reference_urls() -> None:
    source = r"Keep \:quiz, :quiz-extra and [the link][guide]." + "\n\n[guide]: /guide/:quiz[example]"
    assert extract_markers(source) == ([], [])
    assert sanitize_draft(draft(source, []), max_widgets=6).markdown.startswith(source)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Keep :quiz:widget[label] here.", r"Keep \:quiz here."),
        ("Keep :qui:widget[label]z here.", r"Keep \:quiz here."),
        (r"Keep \::quiz here.", r"Keep \: here."),
        ('[Study :quiz](/guide/:quiz[example] ":quiz")', '[Study ](/guide/:quiz[example] ":quiz")'),
    ],
)
def test_inline_cleanup_preserves_adjacent_literal_text_and_link_metadata(source: str, expected: str) -> None:
    assert len(extract_markers(source)[1]) == 1
    cleaned = sanitize_draft(draft(source, []), max_widgets=6)
    assert cleaned.markdown.startswith(expected + "\n")
    assert extract_markers(cleaned.markdown) == ([], [])
