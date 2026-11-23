"""Small calibration report helper.

The production calibration requires ten representative documents and a provider
``count_tokens`` call. This script keeps the calculation reproducible without
making paid network calls by accepting measured pairs from a JSON file.
"""

import json
import sys
from pathlib import Path


def calibration(pairs: list[dict[str, int]]) -> float:
    ratios = [pair["actual"] / pair["estimated"] for pair in pairs if pair["estimated"] > 0]
    if not ratios:
        raise ValueError("No non-empty measurements")
    ratios.sort()
    return round(ratios[min(len(ratios) - 1, int(len(ratios) * 0.95))], 4)


if __name__ == "__main__":
    values = json.loads(Path(sys.argv[1]).read_text())
    print(f"TOKENS_CALIBRATION={calibration(values):.4f}")
