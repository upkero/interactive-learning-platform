"""Output contracts of the quiz generator (story 2.6).

The generator turns quiz directives from the main pass into quiz drafts:
public question data plus a private answer key. The public data is stored
in ``part.content["quizzes"]`` and the answer key in
``part.content["answer_keys"]`` (see ``QuizCheckService``).
"""

from dataclasses import dataclass
from typing import Literal

QuizType = Literal["single_choice", "multiple_choice", "ordering", "numeric"]


@dataclass(frozen=True, slots=True)
class QuizDraft:
    """One quiz generated from a ``kind="quiz"`` directive.

    ``ref`` names the directive slot (e.g. ``q1``). ``key`` is the quiz
    key used in published content and by ``QuizCheckService``. ``type``
    is the quiz kind. ``prompt`` is the question text. ``options`` lists
    choice items (id + text) for single/multiple choice and ordering;
    ``unit`` is the unit for numeric quizzes. ``answer_key`` is the
    private answer key (never shown to the reader).
    """

    ref: str
    key: str
    type: QuizType
    prompt: str
    options: list[dict[str, str]] | None
    unit: str | None
    answer_key: dict[str, object]


__all__ = ["QuizDraft", "QuizType"]
