"""Exercise quiz generation and grading with both LLM calls scripted."""

import pytest
from pydantic import ValidationError

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.services.documents.quiz_check_service import check_answer
from src.app.services.solver.quizzes.quiz_generator import _GeneratedQuiz, _VerifyResult
from tests.support.fakes.llm.llm_client import FakeLLMClient

pytestmark = pytest.mark.unit


async def test_generated_quiz_can_be_graded(monkeypatch: pytest.MonkeyPatch) -> None:
    generated = _GeneratedQuiz.model_validate(
        {
            "key": "q1",
            "type": "single_choice",
            "prompt": "Which data structure uses first-in, first-out ordering?",
            "options": [{"id": "a", "text": "Queue"}, {"id": "b", "text": "Stack"}],
            "correct_id": "a",
            "why_wrong": [{"id": "b", "explanation": "A stack is last-in, first-out."}],
        }
    )
    llm = FakeLLMClient(structured=[generated, _VerifyResult(ok=True)])
    container = ApplicationContainer()
    monkeypatch.setitem(vars(container), "main_llm", llm)
    directive = MainPassDirective(
        ref="q1", kind="quiz", intent="Check queue ordering", source_span="A queue is first-in, first-out."
    )

    (draft,) = await container.quiz_generator.generate(
        directives=[directive], part_title="Queues", part_markdown=directive.source_span
    )

    assert [request.purpose for request in llm.requests] == ["quiz_gen", "quiz_verify"]
    assert draft.ref == directive.ref
    assert draft.options == [{"id": "a", "text": "Queue"}, {"id": "b", "text": "Stack"}]
    result = check_answer({"type": draft.type}, draft.answer_key, "b")
    assert not result.is_correct
    assert result.correct_answer == "a"
    assert result.option_explanations == {"b": "A stack is last-in, first-out."}


def test_generated_ordering_rejects_a_repeated_answer_item() -> None:
    with pytest.raises(ValidationError, match="complete correct_order"):
        _GeneratedQuiz.model_validate(
            {
                "key": "q1",
                "type": "ordering",
                "prompt": "Put the two steps in order.",
                "options": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}],
                "correct_order": ["a", "b", "a"],
            }
        )
