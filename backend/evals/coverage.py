# ruff: noqa: RUF001  # The generated report is intentionally in Russian.
"""Validate the corpus and calculate coverage of explicitly hypothetical intents.

The manifest uses JSON syntax, a subset of YAML, to avoid a runtime YAML
dependency. Nothing in this module calls the model or claims real coverage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED_DISCIPLINES = frozenset({"networks", "os", "algorithms", "databases"})
ALLOWED_LANGUAGES = frozenset({"ru", "en"})
EFFORT = {"S": 1, "M": 2, "L": 3}
FITS = frozenset({"full", "extend", "no"})
CORPUS = Path(__file__).resolve().parent / "corpus"


def read_manifest(path: Path) -> dict[str, Any]:
    """Read the JSON-formatted YAML manifest without depending on the current directory."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be an object")
    return data


def validate_manifest(manifest_path: Path) -> list[str]:
    try:
        data = read_manifest(manifest_path)
    except (OSError, ValueError) as exc:
        return [f"cannot read manifest: {exc}"]
    errors: list[str] = []
    chapters = data.get("chapters")
    if not isinstance(chapters, list):
        return ["chapters must be a list"]
    if not 20 <= len(chapters) <= 30:
        errors.append(f"chapter count must be 20..30, got {len(chapters)}")
    candidates = data.get("candidates")
    if not isinstance(candidates, dict) or not candidates:
        errors.append("candidates must be a non-empty object")
    elif any(
        not isinstance(v, dict) or v.get("effort") not in EFFORT or not v.get("summary") for v in candidates.values()
    ):
        errors.append("every candidate needs a summary and an S/M/L effort")
    ids: set[str] = set()
    disciplines: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    corpus_root = manifest_path.parent.resolve()
    for index, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            errors.append(f"chapter #{index} must be an object")
            continue
        chapter_id = chapter.get("id")
        if not isinstance(chapter_id, str) or not chapter_id:
            errors.append(f"chapter #{index}: id is required")
        elif chapter_id in ids:
            errors.append(f"duplicate chapter id: {chapter_id}")
        else:
            ids.add(chapter_id)
        discipline, lang = chapter.get("discipline"), chapter.get("lang")
        if not isinstance(discipline, str) or discipline not in ALLOWED_DISCIPLINES:
            errors.append(f"{chapter_id}: unsupported discipline {discipline!r}")
        else:
            disciplines[discipline] += 1
        if not isinstance(lang, str) or lang not in ALLOWED_LANGUAGES:
            errors.append(f"{chapter_id}: unsupported language {lang!r}")
        else:
            languages[lang] += 1
        path_value = chapter.get("path")
        if not isinstance(path_value, str) or not path_value:
            errors.append(f"{chapter_id}: path is required")
        else:
            path = (corpus_root / path_value).resolve()
            if corpus_root not in path.parents or not path.is_file():
                errors.append(f"{chapter_id}: missing or unsafe path {path_value}")
            elif path.suffix.lower() != ".md":
                errors.append(f"{chapter_id}: chapter must be Markdown")
            elif chapter.get("sha256") is not None:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if chapter["sha256"] != digest:
                    errors.append(f"{chapter_id}: chapter sha256 does not match manifest")
        for field in ("title", "license", "author"):
            if not isinstance(chapter.get(field), str) or not chapter[field].strip():
                errors.append(f"{chapter_id}: {field} is required")
        source = chapter.get("source")
        if not isinstance(source, str) or not source.startswith(("https://", "http://")):
            errors.append(f"{chapter_id}: source must be an HTTP(S) URL")
        if chapter.get("license") == "private" and not str(path_value).startswith("private/"):
            errors.append(f"{chapter_id}: private license requires private/ path")
    for discipline in sorted(ALLOWED_DISCIPLINES):
        if disciplines[discipline] < 5:
            errors.append(f"{discipline}: need at least 5 chapters, got {disciplines[discipline]}")
    if chapters and languages["en"] * 3 < len(chapters):
        errors.append(f"English chapters must be at least one third, got {languages['en']}/{len(chapters)}")
    if not languages["ru"]:
        errors.append("at least one Russian chapter is required")
    return errors


def read_intents(path: Path, manifest: dict[str, Any], corpus_root: Path) -> dict[str, dict[str, str]]:
    chapters = {chapter["id"]: chapter for chapter in manifest["chapters"]}
    result: dict[str, dict[str, str]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or not all(
            isinstance(row.get(k), str) and row[k].strip()
            for k in ("intent_id", "chapter_id", "description", "source_quote", "source_line", "provenance")
        ):
            raise ValueError(f"invalid hypothetical intent at line {number}")
        intent_id, chapter_id = row["intent_id"], row["chapter_id"]
        if intent_id in result or chapter_id not in chapters:
            raise ValueError(f"duplicate intent or unknown chapter: {intent_id}")
        if row["provenance"] != "hypothetical":
            raise ValueError(f"{intent_id}: only hypothetical intents belong in this dataset")
        text = (corpus_root / chapters[chapter_id]["path"]).read_text(encoding="utf-8").splitlines()
        if not row["source_line"].isdigit() or not 1 <= int(row["source_line"]) <= len(text):
            raise ValueError(f"{intent_id}: invalid source_line")
        if row["source_quote"] not in text[int(row["source_line"]) - 1]:
            raise ValueError(f"{intent_id}: source_quote not found at source_line")
        result[intent_id] = {**row, "discipline": chapters[chapter_id]["discipline"]}
    if not result:
        raise ValueError("intent dataset is empty")
    missing = set(chapters) - {row["chapter_id"] for row in result.values()}
    if missing:
        raise ValueError(f"chapters without hypothetical intents: {', '.join(sorted(missing))}")
    return result


def read_labels(
    path: Path, intents: dict[str, dict[str, str]], candidates: dict[str, Any], *, complete: bool
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"intent_id", "candidate", "fit", "note"} <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: expected intent_id,candidate,fit,note columns")
        for row in reader:
            if any(not isinstance(row.get(field), str) for field in ("intent_id", "candidate", "fit", "note")):
                raise ValueError(f"{path}: incomplete CSV row at line {reader.line_num}")
            intent_id, candidate, fit = row["intent_id"].strip(), row["candidate"].strip(), row["fit"].strip()
            if intent_id in result or intent_id not in intents:
                raise ValueError(f"{path}: duplicate or unknown intent {intent_id}")
            if (
                candidate not in candidates
                and candidate != "not_needed"
                and not re.fullmatch(r"other:[a-z0-9]+(?:-[a-z0-9]+)*", candidate)
            ):
                raise ValueError(f"{path}: unknown candidate {candidate}")
            if fit not in FITS:
                raise ValueError(f"{path}: invalid fit {fit}")
            if (fit in {"extend", "no"} or candidate.startswith("other:")) and not row["note"].strip():
                raise ValueError(f"{path}: {intent_id} needs an explanatory note")
            result[intent_id] = {"candidate": candidate, "fit": fit, "note": row["note"].strip()}
    if complete and set(result) != set(intents):
        raise ValueError(f"{path}: missing labels for {', '.join(sorted(set(intents) - set(result)))}")
    return result


def coverage(
    labels: dict[str, dict[str, str]], selected: set[str], intents: dict[str, dict[str, str]]
) -> dict[str, Any]:
    relevant = [key for key, row in labels.items() if row["candidate"] != "not_needed"]
    if not relevant:
        raise ValueError("coverage is undefined without relevant intentions")
    full = sum(labels[key]["candidate"] in selected and labels[key]["fit"] == "full" for key in relevant)
    extended = sum(
        labels[key]["candidate"] in selected and labels[key]["fit"] in {"full", "extend"} for key in relevant
    )
    disciplines: dict[str, float | None] = {}
    for discipline in sorted(ALLOWED_DISCIPLINES):
        ids = [key for key in relevant if intents[key]["discipline"] == discipline]
        disciplines[discipline] = (
            sum(labels[key]["candidate"] in selected and labels[key]["fit"] in {"full", "extend"} for key in ids)
            / len(ids)
            if ids
            else None
        )
    return {
        "cov": full / len(relevant),
        "cov_plus": extended / len(relevant),
        "cov_d": disciplines,
        "total": len(relevant),
    }


def greedy(
    labels: dict[str, dict[str, str]], intents: dict[str, dict[str, str]], candidates: dict[str, Any], limit: int = 6
) -> list[tuple[str, dict[str, Any]]]:
    selected: set[str] = set()
    steps = []
    while len(selected) < min(limit, len(candidates)):
        # Each intention has one candidate; rank integer gains to avoid float
        # rounding changing an effort tie-break at a non-zero coverage level.
        ranked = sorted(
            (
                -sum(row["candidate"] == name and row["fit"] in {"full", "extend"} for row in labels.values()),
                EFFORT[item["effort"]],
                name,
            )
            for name, item in candidates.items()
            if name not in selected
        )
        gain, _, name = ranked[0]
        if gain == 0:
            break
        selected.add(name)
        steps.append((name, coverage(labels, selected, intents)))
    return steps


def sample_ids(intent_ids: list[str], seed: int = 42) -> list[str]:
    ordered = sorted(intent_ids)
    return sorted(random.Random(seed).sample(ordered, math.ceil(len(ordered) * 0.2)))


def agreement(
    primary: dict[str, dict[str, str]], secondary: dict[str, dict[str, str]], expected: list[str]
) -> float | None:
    if not secondary:
        return None
    if set(secondary) != set(expected):
        raise ValueError("secondary labels must cover exactly the deterministic 20% sample")
    return sum(primary[key]["candidate"] == secondary[key]["candidate"] for key in expected) / len(expected)


def render_report(
    manifest: dict[str, Any],
    intents: dict[str, dict[str, str]],
    labels: dict[str, dict[str, str]],
    secondary: dict[str, dict[str, str]],
) -> str:
    steps = greedy(labels, intents, manifest["candidates"])
    sample = sample_ids(list(intents))
    score = agreement(labels, secondary, sample)
    lines = [
        "# Предполагаемые намерения: демонстрация расчёта покрытия",
        "",
        "> Это искусственно составленная выборка, а не результат MainPass или замер реального покрытия.",
        "> Оценки не подтверждают пороги продукта и не являются независимым ревью.",
        "",
        f"Всего намерений: {len(intents)}; в расчёте: {sum(v['candidate'] != 'not_needed' for v in labels.values())}.",
        "",
        "| Шаг | Добавлен | cov | cov⁺ | algorithms | databases | networks | os |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for index, (name, stats) in enumerate(steps, 1):
        values = [stats["cov_d"][name] for name in sorted(ALLOWED_DISCIPLINES)]
        text = ["—" if value is None else f"{value:.1%}" for value in values]
        lines.append(f"| {index} | `{name}` | {stats['cov']:.1%} | {stats['cov_plus']:.1%} | {' | '.join(text)} |")
    other = Counter(row["candidate"] for row in labels.values() if row["candidate"].startswith("other:"))
    lines += ["", "## Прочие кандидаты", ""]
    lines += [
        f"- `{name}`: {count}" for name, count in sorted(other.items(), key=lambda item: (-item[1], item[0]))[:5]
    ] or ["Нет."]
    lines += ["", "## Повторная разметка", "", f"Выборка: {len(sample)} намерений, seed 42."]
    lines.append(
        "Независимая повторная разметка ещё не проведена; согласие не рассчитано."
        if score is None
        else f"Совпадение candidate: {score:.1%}. Повторный проход выполнен тем же AI и не является независимым."
    )
    lines += [
        "",
        "Пороги 0.6/0.7 и минимум 0.4 по дисциплинам можно применять только к реальному "
        "репрезентативному прогону; здесь решение остаётся гипотезой.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=CORPUS / "manifest.yaml")
    parser.add_argument("--check-manifest", action="store_true")
    parser.add_argument("--intents", type=Path, default=CORPUS / "hypotheses.jsonl")
    parser.add_argument("--labels", type=Path, default=CORPUS / "labels.csv")
    parser.add_argument("--second", type=Path, default=CORPUS / "labels_second.csv")
    parser.add_argument("--output", type=Path, default=CORPUS.parent / "reports" / "coverage.md")
    args = parser.parse_args()
    errors = validate_manifest(args.manifest)
    if errors:
        print("Manifest validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    if args.check_manifest:
        print(f"Manifest validation passed: {args.manifest}")
        return 0
    try:
        manifest = read_manifest(args.manifest)
        intents = read_intents(args.intents, manifest, args.manifest.parent)
        labels = read_labels(args.labels, intents, manifest["candidates"], complete=True)
        second = read_labels(args.second, intents, manifest["candidates"], complete=False)
        report = render_report(manifest, intents, labels, second)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Coverage calculation failed: {exc}")
        return 1
    print(f"Hypothetical coverage report written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
