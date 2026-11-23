"""Directive slots: syntax, checks and sanitising (story 2.2)."""

import random

import pytest

from src.app.contracts.solver.main_pass import DirectiveSpan
from src.app.services.solver.main_pass.directive_parser import (
    DirectiveError,
    check_draft,
    extract_markers,
    locate_spans,
    sanitize_draft,
)
from src.app.services.solver.main_pass.directives import PageDraft
from tests.support.fixtures.main_pass import build_page_draft, load_text

pytestmark = pytest.mark.unit


def test_shared_frontend_examples_are_parsed_the_same_way() -> None:
    # The fixture is shared with the Э6 tests: both sides must agree on it.
    markdown = load_text("directives.md")

    markers = extract_markers(markdown)

    assert [(marker.ref, marker.kind) for marker in markers] == [
        ("w1", "widget"),
        ("i1", "image"),
        ("q1", "quiz"),
    ]
    assert markers[0].attrs["primitive_hint"] == "three-frame"
    assert markers[0].attrs["mode_hint"] == "steps"
    assert markers[1].attrs["image_alias"] == "img-1"


def test_marker_offsets_point_at_the_directive_line() -> None:
    markdown = 'Intro\r\n::widget{ref="w1"}\r\nText\r\n'

    (marker,) = extract_markers(markdown)

    assert marker.line == 2
    assert markdown[marker.start : marker.end] == '::widget{ref="w1"}'
    assert locate_spans(markdown) == (DirectiveSpan(ref="w1", kind="widget", start=7, end=25),)


def test_directives_inside_fenced_code_are_not_slots() -> None:
    markdown = '```markdown\n::widget{ref="w1"}\n```\n::image{ref="i1" image_alias="img-1"}\n'

    assert [(slot.ref, slot.kind) for slot in extract_markers(markdown)] == [("i1", "image")]


def test_inline_directive_is_not_a_slot() -> None:
    markdown = 'Text ::widget{ref="w1"} continues the sentence.\n'

    assert extract_markers(markdown) == ()


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(DirectiveError, match="unknown directive kind 'video'"):
        extract_markers('::video{ref="v1"}')


def test_directive_without_ref_is_rejected() -> None:
    with pytest.raises(DirectiveError, match="has no ref attribute"):
        extract_markers('::widget{mode="single"}')


def test_malformed_directive_is_rejected() -> None:
    with pytest.raises(DirectiveError, match="leaf block"):
        extract_markers('::widget ref="w1"')


def test_check_draft_accepts_the_reference_answer() -> None:
    draft = PageDraft.model_validate(build_page_draft())

    assert check_draft(draft.markdown, draft.directives, image_aliases={"img-1", "img-2"}, max_widgets=4) == []


def test_check_draft_reports_missing_and_undeclared_refs() -> None:
    draft = PageDraft.model_validate(build_page_draft())
    declared = [directive for directive in draft.directives if directive.ref != "i1"]

    violations = check_draft(draft.markdown, declared)

    assert any("has no entry in the directive list" in message for message in violations)


def test_check_draft_reports_a_missing_markdown_directive() -> None:
    draft = PageDraft.model_validate(build_page_draft())
    markdown = draft.markdown.replace('::quiz{ref="q1"}', "")

    violations = check_draft(markdown, draft.directives)

    assert any("directives missing from the markdown: q1" in message for message in violations)


def test_check_draft_checks_image_aliases() -> None:
    draft = PageDraft.model_validate(build_page_draft())

    unknown = check_draft(draft.markdown, draft.directives, image_aliases={"img-2"})
    duplicate = PageDraft.model_validate(
        {
            "markdown": '::image{ref="i1" image_alias="img-1"}\n::image{ref="i2" image_alias="img-1"}\n',
            "directives": [
                {"ref": "i1", "kind": "image", "intent": "One.", "image_alias": "img-1"},
                {"ref": "i2", "kind": "image", "intent": "Two.", "image_alias": "img-1"},
            ],
            "key_terms": ["term"],
        }
    )

    assert any("unknown image alias 'img-1'" in message for message in unknown)
    assert any(
        "used more than once" in message
        for message in check_draft(duplicate.markdown, duplicate.directives, image_aliases={"img-1"})
    )


def test_check_draft_enforces_the_widget_limit() -> None:
    draft = PageDraft.model_validate(build_page_draft())

    violations = check_draft(draft.markdown, draft.directives, max_widgets=0)

    assert any("too many widgets: 1 > 0" in message for message in violations)


def test_check_draft_detects_two_identical_widgets_in_a_row() -> None:
    draft = PageDraft.model_validate(build_page_draft("page_draft_conflict.json"))

    violations = check_draft(draft.markdown, draft.directives, max_widgets=4, alternation=True)

    assert violations == [
        "widgets 'w1' and 'w2' follow each other with primitive 'three-frame' and mode 'steps'; "
        "change the mode, use another primitive, or merge them into one widget"
    ]


def test_text_between_widgets_disables_the_alternation_rule() -> None:
    draft = PageDraft.model_validate(
        {
            "markdown": (
                '::widget{ref="w1" primitive_hint="three-frame" mode_hint="steps"}\n'
                "Some explanation between the two widgets.\n"
                '::widget{ref="w2" primitive_hint="three-frame" mode_hint="steps"}\n'
            ),
            "directives": [
                {
                    "ref": "w1",
                    "kind": "widget",
                    "intent": "One.",
                    "primitive_hint": "three-frame",
                    "mode_hint": "steps",
                },
                {
                    "ref": "w2",
                    "kind": "widget",
                    "intent": "Two.",
                    "primitive_hint": "three-frame",
                    "mode_hint": "steps",
                },
            ],
            "key_terms": ["term"],
        }
    )

    assert check_draft(draft.markdown, draft.directives, alternation=True) == []


def test_sanitize_resets_the_mode_of_the_second_widget() -> None:
    draft = PageDraft.model_validate(build_page_draft("page_draft_conflict.json"))

    sanitized = sanitize_draft(draft, max_widgets=4)

    assert [directive.mode_hint for directive in sanitized.directives] == ["steps", None, None]
    assert check_draft(sanitized.markdown, sanitized.directives, max_widgets=4, alternation=True) == []
    assert sanitize_draft(sanitized, max_widgets=4) == sanitized


def test_sanitize_drops_images_with_unknown_aliases() -> None:
    draft = PageDraft.model_validate(build_page_draft())

    sanitized = sanitize_draft(draft, max_widgets=4, image_aliases={"img-2"})

    assert "i1" not in {directive.ref for directive in sanitized.directives}
    assert "::image" not in sanitized.markdown
    assert check_draft(sanitized.markdown, sanitized.directives, image_aliases={"img-2"}) == []


def test_sanitize_drops_widgets_above_the_limit() -> None:
    draft = PageDraft.model_validate(build_page_draft("page_draft_conflict.json"))

    sanitized = sanitize_draft(draft, max_widgets=1)

    assert [directive.ref for directive in sanitized.directives] == ["w1", "q1"]
    assert sanitized.markdown.count("::widget") == 1
    assert check_draft(sanitized.markdown, sanitized.directives, max_widgets=1, alternation=True) == []


def test_sanitize_draft_property_random_drafts() -> None:
    """Random valid drafts: sanitising removes rule violations and is idempotent."""
    rng = random.Random(20261124)
    for _ in range(120):
        count = rng.randint(1, 7)
        directives: list[dict[str, object]] = []
        lines: list[str] = []
        for index in range(count):
            mode = rng.choice(["steps", "predict", None])
            directives.append(
                {
                    "ref": f"w{index + 1}",
                    "kind": "widget",
                    "intent": f"Show step {index + 1}.",
                    "primitive_hint": "three-frame",
                    "mode_hint": mode,
                }
            )
            attrs = ' primitive_hint="three-frame"' + (f' mode_hint="{mode}"' if mode else "")
            lines.append(f'::widget{{ref="w{index + 1}"{attrs}}}')
            if rng.random() < 0.6:
                lines.append("Some explanation between the widgets.")
        draft = PageDraft.model_validate(
            {"markdown": "\n".join(lines), "directives": directives, "key_terms": ["term"]}
        )

        sanitized = sanitize_draft(draft, max_widgets=10)

        assert check_draft(sanitized.markdown, sanitized.directives, max_widgets=10, alternation=True) == []
        assert sanitize_draft(sanitized, max_widgets=10) == sanitized
