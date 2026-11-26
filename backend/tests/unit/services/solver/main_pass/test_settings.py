import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from src.app.core.settings.solver import SolverSettings


def test_solver_main_pass_defaults() -> None:
    settings = SolverSettings(_env_file=None)
    assert settings.main_pass_max_tokens == 16000
    assert settings.max_widgets_per_part == 6
    assert settings.max_quizzes_per_part == 5
    assert (settings.main_pass_min_key_terms, settings.main_pass_max_key_terms) == (5, 15)


def test_solver_directive_limits_are_configurable(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SOLVER_MAX_WIDGETS_PER_PART", "3")
    monkeypatch.setenv("SOLVER_MAX_QUIZZES_PER_PART", "2")
    settings = SolverSettings(_env_file=None)
    assert settings.max_widgets_per_part == 3
    assert settings.max_quizzes_per_part == 2


@pytest.mark.parametrize(
    ("name", "value"),
    [("SOLVER_MAIN_PASS_MIN_KEY_TERMS", "4"), ("SOLVER_MAIN_PASS_MAX_KEY_TERMS", "16")],
)
def test_key_term_bounds_cannot_diverge_from_schema(monkeypatch: MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        SolverSettings(_env_file=None)
