"""Parameter equality for widget deduplication (story 2.4.5)."""

import json
from typing import Any

NUMBER_TOLERANCE = 0.05


def params_equal(a: Any, b: Any) -> bool:
    """Compare params with ±5% tolerance for numbers, exact for strings/arrays/bools."""
    # Bools must be identical (True != 1)
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b

    # Numbers: ±5% tolerance
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b:
            return True
        max_abs = max(abs(a), abs(b))
        if max_abs == 0:
            return True
        return abs(a - b) <= NUMBER_TOLERANCE * max_abs

    # Dicts: same keys, all values equal recursively
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return False
        return all(params_equal(a[key], b[key]) for key in a)

    # Lists (arrays): exact canonical JSON equality (data arrays like [5,3,8] vs [5,3,8.2])
    if isinstance(a, list) and isinstance(b, list):
        return _canonical(a) == _canonical(b)

    # Everything else: exact equality
    return bool(a == b)


def _canonical(value: Any) -> str:
    """Canonical JSON representation for exact comparison."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


__all__ = ["NUMBER_TOLERANCE", "params_equal"]
