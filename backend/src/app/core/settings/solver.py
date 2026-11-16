from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class SolverSettings(BaseSettings):
    pipeline: Literal["stub", "real"] = "stub"
    model_config = SettingsConfigDict(env_prefix="SOLVER_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_solver_settings() -> SolverSettings:
    return SolverSettings()
