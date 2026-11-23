from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SolverSettings(BaseSettings):
    """Limits of the solver steps; the real part pipeline arrives in story 2.7."""

    pipeline: Literal["stub"] = Field(
        default="stub",
        description="Part pipeline; real is unavailable until story 2.7.",
    )
    main_pass_max_tokens: int = Field(
        default=8192,
        ge=1,
        description=(
            "Max output tokens of one main-pass request. The pass rewrites a whole "
            "part, so this is above the LLMRequest default (story 2.2)."
        ),
    )
    main_pass_max_widgets: int = Field(
        default=4,
        ge=0,
        description="Widget directives allowed in one part; also rendered into the prompt.",
    )
    main_pass_min_key_terms: int = Field(
        default=5,
        ge=1,
        description="Lower bound of key terms per part; rendered into the prompt (story 2.2).",
    )
    main_pass_max_key_terms: int = Field(
        default=12,
        ge=1,
        description="Upper bound of key terms per part; rendered into the prompt (story 2.2).",
    )
    search_overfetch: int = Field(
        default=40,
        ge=1,
        description="Descriptions taken from HNSW before DISTINCT ON (story 2.3).",
    )
    search_max_distance: float = Field(
        default=0.55,
        ge=0.0,
        le=2.0,
        description="Cosine distance above which a candidate is not sent to the reranker (2.3.1).",
    )

    @model_validator(mode="after")
    def validate_key_term_bounds(self) -> Self:
        if self.main_pass_min_key_terms > self.main_pass_max_key_terms:
            raise ValueError("main_pass_min_key_terms must not exceed main_pass_max_key_terms")
        return self

    model_config = SettingsConfigDict(env_prefix="SOLVER_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_solver_settings() -> SolverSettings:
    return SolverSettings()
