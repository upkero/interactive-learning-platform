from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_KEY_TERMS = 5
MAX_KEY_TERMS = 15


class SolverSettings(BaseSettings):
    """Limits of the solver steps; the real part pipeline arrives in story 2.7."""

    pipeline: Literal["stub"] = Field(
        default="stub",
        description="Part pipeline; real is unavailable until story 2.7.",
    )
    main_pass_max_tokens: int = Field(
        default=16000,
        ge=1,
        description=(
            "Max output tokens of one main-pass request. The pass rewrites a whole "
            "part, so this is above the LLMRequest default (story 2.2)."
        ),
    )
    max_widgets_per_part: int = Field(
        default=6,
        ge=0,
        description="Widget directives allowed in one part; also rendered into the prompt.",
    )
    max_quizzes_per_part: int = Field(
        default=5,
        ge=0,
        description="Quiz directives allowed in one part; also rendered into the prompt.",
    )
    main_pass_min_key_terms: int = Field(
        default=MIN_KEY_TERMS,
        ge=MIN_KEY_TERMS,
        le=MIN_KEY_TERMS,
        description="Lower bound of key terms per part; rendered into the prompt (story 2.2).",
    )
    main_pass_max_key_terms: int = Field(
        default=MAX_KEY_TERMS,
        ge=MAX_KEY_TERMS,
        le=MAX_KEY_TERMS,
        description="Upper bound of key terms per part; rendered into the prompt (story 2.2).",
    )

    model_config = SettingsConfigDict(env_prefix="SOLVER_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_solver_settings() -> SolverSettings:
    return SolverSettings()
