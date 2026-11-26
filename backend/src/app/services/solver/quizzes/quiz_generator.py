"""Quiz generator (story 2.6).

Turns ``kind="quiz"`` directives from the main pass into quiz drafts.
For every quiz directive it asks the LLM (``quiz_gen`` purpose) to produce
a question with options and a private answer key, then verifies the result
with a second LLM call (``quiz_verify`` purpose). Verified quizzes are
returned as ``QuizDraft`` objects: public question data for
``part.content["quizzes"]`` and a private answer key for
``part.content["answer_keys"]``.
"""

import logging
from collections.abc import Sequence
from time import perf_counter
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.contracts.solver.quiz_draft import QuizDraft, QuizType
from src.app.core.log_context import bind_log_context
from src.app.core.settings.solver import SolverSettings
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.llm.structured import call_structured

logger = logging.getLogger(__name__)

_GENERATE_DURATION = "quiz_generator.generate_duration_seconds"
_GENERATED_COUNTER = "quiz_generator.generated"
_VERIFIED_COUNTER = "quiz_generator.verified"
_FAILED_COUNTER = "quiz_generator.failed"

_QUIZ_GEN_SYSTEM = """You are the quiz generator of Grasp. You receive a part of a study document and
one quiz directive: a short check that the reader understood the preceding idea.

Produce one quiz question that can be answered from the part text alone. Do not invent
facts, examples or numbers that the source does not contain. Match the reader profile:
novice needs simple, concrete questions; advanced needs precision and edge cases.

Supported types:
- single_choice — one correct option among 4; give correct_id and why_wrong entries for the distractors.
- multiple_choice — 2-4 correct options among 5-6; give correct_ids and why_wrong entries for the distractors.
- ordering — 4-5 items to put in the correct order; give correct_order and common_mistakes.
- numeric — one numeric answer with unit; give answer, tolerance and common_mistakes.

Every why_wrong entry gives the distractor id and its explanation.
Answer with the JSON object required by the response schema."""

_QUIZ_VERIFY_SYSTEM = """You are the quiz verifier of Grasp. You receive a quiz question, its answer key
and the source part text. Check that:

1. The question can be answered from the part text alone.
2. The answer key is consistent with the question (exactly one correct answer for
   single_choice, at least one for multiple_choice, a full ordering for ordering,
   a plausible numeric answer with tolerance for numeric).
3. No option text duplicates another option's text.
4. Explanations are short and accurate.

Reply with a JSON object: {"ok": true} if the quiz passes, or
{"ok": false, "reason": "..."} if it needs regeneration."""


class _QuizOption(BaseModel):
    id: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=200)


class _DistractorExplanation(BaseModel):
    id: str = Field(min_length=1, max_length=8)
    explanation: str = Field(min_length=1, max_length=300)


class _GeneratedQuiz(BaseModel):
    """Structured LLM output for one generated quiz (public data + answer key)."""

    key: str = Field(min_length=1, max_length=12)
    type: QuizType
    prompt: str = Field(min_length=1, max_length=500)
    options: list[_QuizOption] | None = None
    unit: str | None = Field(default=None, max_length=32)
    # answer key (private)
    correct_id: str | None = None
    correct_ids: list[str] | None = None
    correct_order: list[str] | None = None
    answer: float | None = Field(default=None, allow_inf_nan=False)
    tolerance: float = Field(default=0.01, ge=0, allow_inf_nan=False)
    explanation: str | None = Field(default=None, max_length=300)
    why_wrong: list[_DistractorExplanation] | None = None
    common_mistakes: list[str] | None = None

    @model_validator(mode="after")
    def _validate_key_fields(self) -> "_GeneratedQuiz":
        kind = self.type
        options = self.options or []
        option_ids = {option.id for option in options}
        if len(option_ids) != len(options):
            raise ValueError("option ids must be unique")
        if kind == "single_choice":
            if len(options) < 2:
                raise ValueError("single_choice needs at least 2 options")
            if self.correct_id not in option_ids:
                raise ValueError("single_choice needs a valid correct_id")
        elif kind == "multiple_choice":
            if len(options) < 2:
                raise ValueError("multiple_choice needs at least 2 options")
            if not self.correct_ids or not set(self.correct_ids) <= option_ids:
                raise ValueError("multiple_choice needs valid correct_ids")
            if len(set(self.correct_ids)) != len(self.correct_ids):
                raise ValueError("multiple_choice correct_ids must be unique")
        elif kind == "ordering":
            if len(options) < 2:
                raise ValueError("ordering needs at least 2 items")
            order = self.correct_order or []
            if len(order) != len(options) or set(order) != option_ids:
                raise ValueError("ordering needs a complete correct_order")
        elif kind == "numeric":
            if self.answer is None:
                raise ValueError("numeric needs an answer")
        return self


class QuizGenerator:
    """Generate quiz questions from quiz directives."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        settings: SolverSettings,
        metrics: MetricsCollector,
    ) -> None:
        self._llm = llm
        self._settings = settings
        self._metrics = metrics

    async def generate(
        self,
        *,
        directives: Sequence[MainPassDirective],
        part_title: str,
        part_markdown: str,
    ) -> list[QuizDraft]:
        """Generate one quiz per ``kind="quiz"`` directive.

        Returns quiz drafts in directive order. Directives that fail
        generation or verification are skipped and counted as failures.
        """
        quiz_directives = [d for d in directives if d.kind == "quiz"]
        if not quiz_directives:
            return []

        started = perf_counter()
        generated = 0
        verified = 0
        failed = 0
        drafts: list[QuizDraft] = []

        try:
            for directive in quiz_directives:
                with bind_log_context(part_title=part_title, directive_ref=directive.ref):
                    try:
                        quiz = await self._generate_one(
                            directive=directive,
                            part_title=part_title,
                            part_markdown=part_markdown,
                        )
                        drafts.append(quiz)
                        generated += 1
                        verified += 1
                    except Exception:
                        logger.exception("Quiz generation failed for directive %r.", directive.ref)
                        failed += 1
        finally:
            self._metrics.observe_histogram(_GENERATE_DURATION, perf_counter() - started)
            self._metrics.increment_counter(_GENERATED_COUNTER, by=generated)
            self._metrics.increment_counter(_VERIFIED_COUNTER, by=verified)
            self._metrics.increment_counter(_FAILED_COUNTER, by=failed)

        return drafts

    async def _generate_one(
        self,
        *,
        directive: MainPassDirective,
        part_title: str,
        part_markdown: str,
    ) -> QuizDraft:
        request = self._build_request(directive, part_title, part_markdown)
        generated = await call_structured(self._llm, request, _GeneratedQuiz)
        verified = await self._verify(generated, part_markdown)
        if not verified:
            raise ValueError("quiz failed verification")
        return self._to_draft(directive.ref, generated)

    def _build_request(
        self,
        directive: MainPassDirective,
        part_title: str,
        part_markdown: str,
    ) -> LLMRequest:
        system = SystemBlock(_QUIZ_GEN_SYSTEM, cache=True)
        context = (
            f"<part_title>{part_title}</part_title>\n"
            f"<part>\n{part_markdown}\n</part>\n"
            f'<quiz directive ref="{directive.ref}" intent="{directive.intent}" />\n'
        )
        return LLMRequest(
            purpose="quiz_gen",
            system=(system,),
            messages=(
                LLMMessage(
                    role="user",
                    content=context,
                ),
            ),
            max_tokens=self._settings.main_pass_max_tokens,
            metadata={"directive_ref": directive.ref, "directive_kind": directive.kind},
        )

    async def _verify(self, quiz: _GeneratedQuiz, part_markdown: str) -> bool:
        context = f"<quiz>\n{quiz.model_dump_json()}\n</quiz>\n<part>\n{part_markdown}\n</part>\n"
        request = LLMRequest(
            purpose="quiz_verify",
            system=(SystemBlock(_QUIZ_VERIFY_SYSTEM, cache=True),),
            messages=(LLMMessage(role="user", content=context),),
            max_tokens=1024,
            metadata={"quiz_key": quiz.key},
        )
        try:
            result = await call_structured(self._llm, request, _VerifyResult)
        except Exception:
            logger.exception("Quiz verification call failed for %s.", quiz.key)
            return False
        return result.ok

    @staticmethod
    def _to_draft(ref: str, quiz: _GeneratedQuiz) -> QuizDraft:
        key = quiz.key or f"q{uuid4().hex[:8]}"
        options = [{"id": o.id, "text": o.text} for o in quiz.options] if quiz.options is not None else None
        why_wrong = {item.id: item.explanation for item in quiz.why_wrong} if quiz.why_wrong is not None else None
        answer_key: dict[str, object] = {}
        if quiz.type == "single_choice":
            answer_key = {
                "correct_id": quiz.correct_id,
                "explanation": quiz.explanation,
                "why_wrong": why_wrong,
            }
        elif quiz.type == "multiple_choice":
            answer_key = {
                "correct_ids": quiz.correct_ids,
                "explanation": quiz.explanation,
                "why_wrong": why_wrong,
            }
        elif quiz.type == "ordering":
            answer_key = {
                "correct_order": quiz.correct_order,
                "explanation": quiz.explanation,
                "common_mistakes": quiz.common_mistakes,
            }
        elif quiz.type == "numeric":
            answer_key = {
                "answer": quiz.answer,
                "tolerance": quiz.tolerance,
                "explanation": quiz.explanation,
                "common_mistakes": quiz.common_mistakes,
            }
        return QuizDraft(
            ref=ref,
            key=key,
            type=quiz.type,
            prompt=quiz.prompt,
            options=options,
            unit=quiz.unit,
            answer_key=answer_key,
        )


class _VerifyResult(BaseModel):
    ok: bool
    reason: str | None = None


__all__ = ["QuizGenerator", "QuizType"]
