"""System block of a request.

Shared context (system prompt of the step, user profile, topic tree) goes
first with ``cache=True`` — the only way to make prompt caching fire and
keep provider calls cheap. Volatile content (the part text) must strictly
follow cached blocks.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SystemBlock:
    text: str
    cache: bool = False  # пометить блок cache_control: ephemeral
