"""Tests for the main pass wire schema and source quotation offsets."""

import pytest
from pydantic import ValidationError

from src.app.services.solver.main_pass.directives import Directive, PageDraft
from src.app.services.solver.main_pass.source_spans import locate_spans

pytestmark = pytest.mark.unit


def directive(**updates: object) -> Directive:
    data: dict[str, object] = {
        "ref": "w1",
        "kind": "widget",
        "intent": "Explain the process",
        "source_span": "a quoted fragment",
    }
    data.update(updates)
    return Directive.model_validate(data)


def test_schema_keeps_inconsistent_draft_for_service_to_repair() -> None:
    draft = PageDraft(markdown="x" * 200, directives=[directive()], key_terms=["term"] * 5)
    assert draft.to_draft().directives[0].source_span == "a quoted fragment"


@pytest.mark.parametrize("ref", ["w0", "w100", "wabc", "widget"])
def test_ref_format(ref: str) -> None:
    with pytest.raises(ValidationError):
        directive(ref=ref)


def test_kind_specific_fields() -> None:
    image = directive(ref="img_1", kind="image", image_id="img_1")
    assert image.image_id == "img_1"
    assert directive(ref="q1", kind="quiz", params_hint="numeric").params_hint == "numeric"
    for updates in (
        {"ref": "img_1", "kind": "image", "image_id": "img_2"},
        {"ref": "img_1", "kind": "image", "image_id": "img_1", "params_hint": "data"},
        {"mode_hint": "dance"},
    ):
        with pytest.raises(ValidationError):
            directive(**updates)


def test_source_offsets_found_missing_and_whitespace() -> None:
    source = "Prefix: a quoted\n   fragment. suffix"
    found, missing = locate_spans([directive(), directive(ref="w2", source_span="not in the source")], source)
    assert found.start is not None and found.end is not None
    assert source[found.start : found.end] == "a quoted\n   fragment"
    assert missing.start is None and missing.end is None
