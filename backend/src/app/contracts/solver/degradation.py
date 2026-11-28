"""Degradation tracking for the resolver (story 2.4).

A Degradation records that a resolver stage failed and the algorithm
fell back to the next branch. The InstrumentedResolver aggregates these
into the decision log and Prometheus metrics.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Degradation:
    """One resolver stage that failed and triggered a fallback."""

    stage: str
    reason: str
    fallback: str


__all__ = ["Degradation"]
