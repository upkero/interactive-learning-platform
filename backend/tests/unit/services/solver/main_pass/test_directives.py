"""PageDraft: the answer schema and its conversion to the contracts."""

import pytest
from pydantic import ValidationError

from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.services.solver.main_pass.directives import Directive, PageDraft
from tests.support.fixtures.main_pass import build_page_draft

pytestmark = pytest.mark.unit


def test_reference_answer_validates_and_converts_to_contracts() -> None:
    draft = PageDraft.model_validate(build_page_draft())

    output = draft.to_draft()

    assert output.markdown.startswith("## From neurons to layers")
    assert output.directives == (
        MainPassDirective(
            ref="w1",
            kind="widget",
            intent="Show how the weighted sum of three inputs becomes one neuron output.",
            primitive_hint="three-frame",
            mode_hint="steps",
        ),
        MainPassDirective(
            ref="i1",
            kind="image",
            intent="The diagram of a single neuron with three inputs from the source part.",
            image_alias="img-1",
        ),
        MainPassDirective(
            ref="q1",
            kind="quiz",
            intent="Check that the reader can tell a weight from an activation function.",
        ),
    )
    assert output.key_terms == ("neuron", "weight", "bias", "activation function", "layer", "ReLU")


def test_all_three_directive_kinds_are_validated() -> None:
    draft = PageDraft.model_validate(build_page_draft())

    assert {directive.kind for directive in draft.directives} == {"widget", "image", "quiz"}


@pytest.mark.parametrize(
    "payload",
    (
        {
            "ref": "i1",
            "kind": "widget",
            "intent": "Wrong prefix.",
        },
        {
            "ref": "w1",
            "kind": "image",
            "intent": "Missing alias.",
        },
        {
            "ref": "q1",
            "kind": "quiz",
            "intent": "Hints are not allowed.",
            "mode_hint": "steps",
        },
        {
            "ref": "w1",
            "kind": "widget",
            "intent": "Alias is not allowed.",
            "image_alias": "img-1",
        },
        {
            "ref": "w1",
            "kind": "widget",
            "intent": "Unknown field.",
            "invented": True,
        },
    ),
)
def test_directive_fields_must_match_the_kind(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Directive.model_validate(payload)


def test_page_draft_forbids_unknown_fields() -> None:
    payload = build_page_draft()
    payload["schema_version"] = 1

    with pytest.raises(ValidationError):
        PageDraft.model_validate(payload)


def test_directive_list_must_match_the_markdown() -> None:
    payload = build_page_draft()
    payload["directives"] = payload["directives"][1:]  # w1 stays in the markdown only

    with pytest.raises(ValidationError, match="markdown directive 'w1' has no entry"):
        PageDraft.model_validate(payload)


def test_a_draft_without_directives_is_valid() -> None:
    draft = PageDraft(markdown="Plain page without interactive elements.", key_terms=["term"])

    assert draft.directives == []


def test_key_terms_are_required() -> None:
    with pytest.raises(ValidationError):
        PageDraft(markdown="Page.", key_terms=[])


def test_ref_is_a_short_identifier() -> None:
    with pytest.raises(ValidationError):
        PageDraft(
            markdown='::widget{ref="has space"}\n',
            directives=[{"ref": "has space", "kind": "widget", "intent": "Show it."}],
            key_terms=["term"],
        )


def test_strings_are_trimmed() -> None:
    draft = PageDraft(markdown="  Page body.\n", key_terms=["  term  "])

    output = draft.to_draft()

    assert output.markdown == "Page body."
    assert output.key_terms == ("term",)


def test_conflict_fixture_is_structurally_valid() -> None:
    # Alternation is a service-level rule: it needs part context and a repair
    # turn, so the schema itself must accept the draft.
    draft = PageDraft.model_validate(build_page_draft("page_draft_conflict.json"))

    assert [directive.ref for directive in draft.directives] == ["w1", "w2", "q1"]
