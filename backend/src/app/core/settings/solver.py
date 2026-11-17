from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SolverSettings(BaseSettings):
    """Select the part pipeline; the real implementation arrives in story 2.7."""

    pipeline: Literal["stub"] = Field(default="stub", description="Part pipeline; real is unavailable until story 2.7.")
    model_config = SettingsConfigDict(env_prefix="SOLVER_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_solver_settings() -> SolverSettings:
    return SolverSettings()
