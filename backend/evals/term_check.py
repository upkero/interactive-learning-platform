"""Check five reference parts against saved model outputs, not hand-written drafts.

Run ``python -m evals.term_check [outputs_dir]``. Each case needs a JSON file
named ``<case-id>.json`` containing ``model``, ``prompt_version``,
``generated_at`` and ``draft`` (with ``markdown`` and ``key_terms``). These
metadata document provenance; the checker cannot prove the output is genuine.
"""

import json
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, TypeGuard


def missing_terms(part_text: str, key_terms: Iterable[str]) -> list[str]:
    """Return terms absent verbatim (including case) from the output."""
    return [term for term in key_terms if term not in part_text]


def _read_json(path: Path, problems: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        problems.append(f"{path}: cannot read JSON: {exc}")
        return None
    if not isinstance(value, dict):
        problems.append(f"{path}: expected a JSON object")
        return None
    return value


def _terms(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and bool(value) and all(isinstance(term, str) and term.strip() for term in value)


def check_reference_parts(fixtures: Path | None = None, outputs: Path | None = None) -> list[str]:
    """Report incomplete inputs, absent snapshots and missing verbatim terms."""
    root = fixtures or Path(__file__).resolve().parents[1] / "tests" / "support" / "fixtures" / "main_pass"
    outputs = outputs or root / "reference_corpus" / "outputs_sonnet55"
    problems: list[str] = []
    document = _read_json(root / "document.json", problems)
    manifest = _read_json(root / "reference_corpus" / "manifest.json", problems)
    if document is None or manifest is None:
        return problems
    parts = document.get("parts")
    cases = manifest.get("cases")
    if not isinstance(parts, list) or len(parts) != 2 or not isinstance(cases, list) or len(cases) != 3:
        return [*problems, "Expected two document parts and three reference corpus cases."]

    records: list[tuple[object, object, Path, object]] = []
    for part in parts:
        if not isinstance(part, dict):
            problems.append("Invalid document part entry.")
            continue
        records.append((part.get("key"), part.get("glossary"), root, part.get("markdown")))
    for case in cases:
        if not isinstance(case, dict):
            problems.append("Invalid reference corpus case entry.")
            continue
        records.append((case.get("id"), case.get("glossary"), root / "reference_corpus", case.get("source")))

    seen: set[str] = set()
    for case_id, glossary, source_root, source_name in records:
        if not isinstance(case_id, str) or not case_id or Path(case_id).name != case_id or case_id in seen:
            problems.append(f"Invalid or duplicate case ID: {case_id!r}")
            continue
        seen.add(case_id)
        if not _terms(glossary):
            problems.append(f"{case_id}: glossary must be a non-empty list of terms")
        if not isinstance(source_name, str) or Path(source_name).name != source_name:
            problems.append(f"{case_id}: missing or invalid source filename")
        else:
            try:
                source = (source_root / source_name).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                problems.append(f"{case_id}: cannot read source: {exc}")
            else:
                if _terms(glossary):
                    missing = missing_terms(source, glossary)
                    if missing:
                        problems.append(f"{case_id}: glossary missing from source: {', '.join(missing)}")

        snapshot = _read_json(outputs / f"{case_id}.json", problems)
        if snapshot is None:
            continue
        for field in ("model", "prompt_version", "generated_at"):
            if not isinstance(snapshot.get(field), str) or not snapshot[field].strip():
                problems.append(f"{case_id}: snapshot requires non-empty {field}")
        draft = snapshot.get("draft")
        if not isinstance(draft, dict) or not isinstance(draft.get("markdown"), str) or not draft["markdown"].strip():
            problems.append(f"{case_id}: snapshot requires non-empty draft markdown")
            continue
        key_terms = draft.get("key_terms")
        if not _terms(key_terms):
            problems.append(f"{case_id}: snapshot requires non-empty key terms")
        for label, terms in (("key terms", key_terms), ("glossary", glossary)):
            if _terms(terms):
                missing = missing_terms(draft["markdown"], terms)
                if missing:
                    problems.append(f"{case_id}: {label} missing from output: {', '.join(missing)}")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        print("usage: python -m evals.term_check [outputs_dir]", file=sys.stderr)
        return 2
    problems = check_reference_parts(outputs=Path(args[0]) if args else None)
    if problems:
        for problem in problems:
            print(f"term-check: {problem}", file=sys.stderr)
        return 1
    print("term-check: all five snapshots contain their glossary and key terms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
