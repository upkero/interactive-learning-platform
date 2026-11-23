"""Terminology check of the main-pass drafts (story 2.2.1).

The pass must keep the source terminology: every key term has to occur in
the source part, in the source language, without translation or synonyms.
The check normalises whitespace and case; it is used by the unit test and
can be run over the reference corpus:

    python -m evals.term_check [fixture_dir]
"""

import json
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path


def missing_terms(part_text: str, key_terms: Iterable[str]) -> list[str]:
    """Terms of ``key_terms`` that do not occur in ``part_text``."""
    normalized = " ".join(part_text.split()).casefold()
    return [term for term in key_terms if " ".join(term.split()).casefold() not in normalized]


def check_reference_parts(fixtures: Path | None = None) -> list[str]:
    """Return one human-readable problem per reference part with a bad draft."""
    root = (
        fixtures
        if fixtures is not None
        else Path(__file__).resolve().parents[1] / "tests" / "support" / "fixtures" / "main_pass"
    )
    document = json.loads((root / "document.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    for part in document["parts"]:
        source = (root / part["markdown"]).read_text(encoding="utf-8")
        draft = json.loads((root / part["draft"]).read_text(encoding="utf-8"))
        missing = missing_terms(source, draft["key_terms"])
        if missing:
            problems.append(f"{part['key']}: key terms missing from the source: {', '.join(missing)}")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    problems = check_reference_parts(Path(args[0]) if args else None)
    if problems:
        for problem in problems:
            print(f"term-check: {problem}", file=sys.stderr)
        return 1
    print("term-check: every key term occurs in its source part.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
