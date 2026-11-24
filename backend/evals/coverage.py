"""Validate the corpus and calculate primitive coverage from labeled intentions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlparse

import yaml

Discipline = Literal["networks", "os", "algorithms", "databases"]
Fit = Literal["full", "extend", "no"]
Provenance = Literal["hypothetical", "main_pass"]
ALLOWED_DISCIPLINES = frozenset({"networks", "os", "algorithms", "databases"})
FITS = frozenset({"full", "extend", "no"})
COVERING_FITS = frozenset({"full", "extend"})
EFFORT = {"S": 1, "M": 2, "L": 3}
SECOND_LABEL_SHARE = 0.2
SECOND_LABEL_SEED = 42
CORPUS = Path(__file__).resolve().parent / "corpus"


class CorpusError(ValueError):
    """Invalid corpus data, with a human-readable diagnostic."""


@dataclass(frozen=True, slots=True)
class Candidate:
    effort: str
    summary: str


@dataclass(frozen=True, slots=True)
class Chapter:
    id: str
    discipline: Discipline
    lang: str
    title: str
    path: str
    source: str
    license: str
    author: str = ""
    sha256: str = ""


@dataclass(frozen=True, slots=True)
class Manifest:
    chapters: tuple[Chapter, ...]
    candidates: dict[str, Candidate]
    root: Path


@dataclass(frozen=True, slots=True)
class Intent:
    id: str
    chapter_id: str
    discipline: Discipline
    description: str
    source_span: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class IntentSet:
    items: dict[str, Intent]
    provenance: Provenance
    prompt_sha: str = ""
    model: str = ""


@dataclass(frozen=True, slots=True)
class Label:
    intent_id: str
    candidate: str
    fit: Fit
    note: str = ""


@dataclass(frozen=True, slots=True)
class CoverageStats:
    cov: float
    cov_plus: float
    cov_d: dict[str, float | None]
    total: int


@dataclass(frozen=True, slots=True)
class GreedyStep:
    candidate: str
    stats: CoverageStats


def _required(row: dict[str, object], key: str, context: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CorpusError(f"{context}: {key} must be a non-empty string")
    return value.strip()


def read_manifest(path: Path) -> Manifest:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CorpusError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("chapters"), list):
        raise CorpusError("manifest root must contain a chapters list")
    raw_candidates = data.get("candidates")
    if not isinstance(raw_candidates, dict) or not raw_candidates:
        raise CorpusError("candidates must be a non-empty object")
    candidates = {}
    for name, row in raw_candidates.items():
        if not isinstance(name, str) or not isinstance(row, dict):
            raise CorpusError("candidate must have an id and an object")
        effort = _required(row, "effort", name)
        if effort not in EFFORT:
            raise CorpusError(f"{name}: effort must be S, M or L")
        candidates[name] = Candidate(effort, _required(row, "summary", name))
    chapters = []
    for index, row in enumerate(data["chapters"], 1):
        if not isinstance(row, dict):
            raise CorpusError(f"chapter #{index} must be an object")
        cid = _required(row, "id", f"chapter #{index}")
        discipline = _required(row, "discipline", cid)
        if discipline not in ALLOWED_DISCIPLINES:
            raise CorpusError(f"{cid}: unsupported discipline {discipline}")
        chapters.append(
            Chapter(
                cid,
                cast(Discipline, discipline),
                _required(row, "lang", cid),
                _required(row, "title", cid),
                _required(row, "path", cid),
                _required(row, "source", cid),
                _required(row, "license", cid),
                str(row.get("author") or ""),
                str(row.get("sha256") or ""),
            )
        )
    return Manifest(tuple(chapters), candidates, path.parent.resolve())


def _validate_chapter(chapter: Chapter, root: Path) -> list[str]:
    errors = []
    path = (root / chapter.path).resolve()
    if chapter.lang not in {"ru", "en"}:
        errors.append(f"{chapter.id}: unsupported language {chapter.lang}")
    if root not in path.parents or not path.is_file():
        errors.append(f"{chapter.id}: missing or unsafe path {chapter.path}")
    elif path.suffix.lower() != ".md":
        errors.append(f"{chapter.id}: chapter must be Markdown")
    elif chapter.sha256 and hashlib.sha256(path.read_bytes()).hexdigest() != chapter.sha256:
        errors.append(f"{chapter.id}: chapter sha256 does not match manifest")
    if chapter.license == "private" and not chapter.path.startswith("private/"):
        errors.append(f"{chapter.id}: private license requires private/ path")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", chapter.source):
        parsed = urlparse(chapter.source)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{chapter.id}: invalid source URL")
    return errors


def _validate_totals(chapters: tuple[Chapter, ...]) -> list[str]:
    errors = []
    if not 20 <= len(chapters) <= 30:
        errors.append(f"chapter count must be 20..30, got {len(chapters)}")
    ids = Counter(c.id for c in chapters)
    errors.extend(f"duplicate chapter id: {cid}" for cid, count in ids.items() if count > 1)
    counts: Counter[str] = Counter(c.discipline for c in chapters)
    errors.extend(
        f"{d}: need at least 5 chapters, got {counts[d]}" for d in sorted(ALLOWED_DISCIPLINES) if counts[d] < 5
    )
    if sum(c.lang == "en" for c in chapters) * 3 < len(chapters):
        errors.append("English chapters must be at least one third")
    if not any(c.lang == "ru" for c in chapters):
        errors.append("at least one Russian chapter is required")
    return errors


def validate_manifest(manifest: Manifest) -> list[str]:
    return _validate_totals(manifest.chapters) + [
        error for c in manifest.chapters for error in _validate_chapter(c, manifest.root)
    ]


def read_intents(path: Path, manifest: Manifest) -> IntentSet:
    chapters = {c.id: c for c in manifest.chapters}
    cache: dict[str, list[str]] = {}
    result: dict[str, Intent] = {}
    metadata: dict[str, str] = {}
    origin: str | None = None
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorpusError(f"{path}:{number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise CorpusError(f"{path}:{number}: expected object")
        if not result and not metadata and "intent_id" not in row:
            metadata = {key: str(row[key]) for key in ("prompt_sha", "model", "provenance") if key in row}
            continue
        context = f"{path}:{number}"
        iid, cid = _required(row, "intent_id", context), _required(row, "chapter_id", context)
        if iid in result or cid not in chapters:
            raise CorpusError(f"{context}: duplicate intent or unknown chapter: {iid}")
        provenance = row.get("provenance", metadata.get("provenance", "main_pass"))
        if provenance not in {"main_pass", "hypothetical"} or (origin and provenance != origin):
            raise CorpusError(f"{context}: invalid or mixed provenance")
        origin = provenance
        description = _required(row, "intent", context)
        span = _required(row, "source_span", context)
        if "source_line" in row:
            raw_line = str(row["source_line"])
            if cid not in cache:
                cache[cid] = (manifest.root / chapters[cid].path).read_text(encoding="utf-8").splitlines()
            lines = cache[cid]
            if not raw_line.isdigit() or not 1 <= int(raw_line) <= len(lines) or span not in lines[int(raw_line) - 1]:
                raise CorpusError(f"{iid}: source_span not found at source_line")
        result[iid] = Intent(iid, cid, chapters[cid].discipline, description, span, cast(Provenance, provenance))
    if not result:
        raise CorpusError("intent dataset is empty")
    missing = set(chapters) - {row.chapter_id for row in result.values()}
    if missing:
        raise CorpusError(f"chapters without intents: {', '.join(sorted(missing))}")
    return IntentSet(result, cast(Provenance, origin), metadata.get("prompt_sha", ""), metadata.get("model", ""))


def read_labels(
    path: Path, intents: IntentSet, candidates: dict[str, Candidate], *, complete: bool
) -> dict[str, Label]:
    result: dict[str, Label] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"intent_id", "candidate", "fit", "note"} <= set(reader.fieldnames or []):
            raise CorpusError(f"{path}: expected intent_id,candidate,fit,note columns")
        for row in reader:
            if any(not isinstance(row.get(field), str) for field in ("intent_id", "candidate", "fit", "note")):
                raise CorpusError(f"{path}: incomplete CSV row at line {reader.line_num}")
            iid, candidate, fit, note = (row[k].strip() for k in ("intent_id", "candidate", "fit", "note"))
            if iid in result or iid not in intents.items:
                raise CorpusError(f"{path}: duplicate or unknown intent {iid}")
            if (
                candidate not in candidates
                and candidate != "not_needed"
                and not re.fullmatch(r"other:[a-z0-9]+(?:-[a-z0-9]+)*", candidate)
            ):
                raise CorpusError(f"{path}: unknown candidate {candidate}")
            if fit not in FITS:
                raise CorpusError(f"{path}: invalid fit {fit}")
            if (fit in {"extend", "no"} or candidate.startswith("other:")) and not note:
                raise CorpusError(f"{path}: {iid} needs an explanatory note")
            result[iid] = Label(iid, candidate, cast(Fit, fit), note)
    if complete and set(result) != set(intents.items):
        raise CorpusError(f"{path}: incomplete labels")
    return result


def _covered(label: Label, selected: set[str]) -> bool:
    return label.candidate in selected and label.fit in COVERING_FITS


def coverage(labels: dict[str, Label], selected: set[str], intents: IntentSet) -> CoverageStats:
    relevant = [label for label in labels.values() if label.candidate != "not_needed"]
    if not relevant:
        raise CorpusError("coverage is undefined without relevant intentions")
    by_discipline: dict[str, float | None] = {}
    for discipline in sorted(ALLOWED_DISCIPLINES):
        group = [label for label in relevant if intents.items[label.intent_id].discipline == discipline]
        by_discipline[discipline] = sum(_covered(label, selected) for label in group) / len(group) if group else None
    return CoverageStats(
        sum(x.candidate in selected and x.fit == "full" for x in relevant) / len(relevant),
        sum(_covered(x, selected) for x in relevant) / len(relevant),
        by_discipline,
        len(relevant),
    )


def greedy(
    labels: dict[str, Label], intents: IntentSet, candidates: dict[str, Candidate], limit: int = 6
) -> list[GreedyStep]:
    selected: set[str] = set()
    available = {label.candidate for label in labels.values()} - {"not_needed"}
    steps = []
    while available and len(selected) < limit:
        ranked = sorted(
            (
                -sum(_covered(label, {name}) for label in labels.values()),
                EFFORT[candidates[name].effort] if name in candidates else EFFORT["L"],
                name,
            )
            for name in available
        )
        gain, _, name = ranked[0]
        if gain == 0:
            break
        selected.add(name)
        available.remove(name)
        steps.append(GreedyStep(name, coverage(labels, selected, intents)))
    return steps


def sample_ids(intent_ids: list[str], seed: int = SECOND_LABEL_SEED) -> list[str]:
    return sorted(random.Random(seed).sample(sorted(intent_ids), math.ceil(len(intent_ids) * SECOND_LABEL_SHARE)))


def agreement(primary: dict[str, Label], secondary: dict[str, Label], expected: list[str]) -> float | None:
    if not secondary:
        return None
    if set(secondary) != set(expected):
        raise CorpusError("secondary labels must cover exactly the deterministic 20% sample")
    return sum(primary[key].candidate == secondary[key].candidate for key in expected) / len(expected)


def top_other(labels: dict[str, Label]) -> list[tuple[str, int]]:
    counts = Counter(label.candidate for label in labels.values() if label.candidate.startswith("other:"))
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]


def render_report(
    manifest: Manifest,
    intents: IntentSet,
    labels: dict[str, Label],
    secondary: dict[str, Label],
    *,
    seed: int = SECOND_LABEL_SEED,
) -> str:
    sample = sample_ids(list(intents.items), seed)
    score = agreement(labels, secondary, sample)
    lines = ["# Расчёт покрытия примитивами", ""]
    if intents.provenance == "hypothetical":
        lines += ["> Это искусственная выборка, не результат MainPass и не измерение реального покрытия.", ""]
    else:
        lines += [
            f"Источник: MainPass; prompt_sha: {intents.prompt_sha or 'не указан'}; "
            f"модель: {intents.model or 'не указана'}.",
            "",
        ]
    relevant_count = sum(x.candidate != "not_needed" for x in labels.values())
    lines += [
        f"Всего намерений: {len(intents.items)}; в расчёте: {relevant_count}.",  # noqa: RUF001
        "",
        "| Шаг | Добавлен | cov | cov⁺ | algorithms | databases | networks | os |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for index, step in enumerate(greedy(labels, intents, manifest.candidates), 1):
        values = [step.stats.cov_d[d] for d in sorted(ALLOWED_DISCIPLINES)]
        formatted = ["—" if value is None else f"{value:.1%}" for value in values]
        lines.append(
            f"| {index} | `{step.candidate}` | {step.stats.cov:.1%} | "
            f"{step.stats.cov_plus:.1%} | {' | '.join(formatted)} |"
        )
    lines += ["", "## Прочие кандидаты", ""] + (
        [f"- `{name}`: {count}" for name, count in top_other(labels)] or ["Нет."]
    )
    lines += ["", "## Повторная разметка", "", f"Выборка: {len(sample)} намерений, seed {seed}."]
    lines.append("Согласие не рассчитано." if score is None else f"Совпадение candidate: {score:.1%}.")
    if intents.provenance == "hypothetical":
        lines += [
            "Повторный проход выполнен тем же AI и не является независимым.",
            "",
            "Пороги нельзя оценивать на искусственных данных.",
        ]
    return "\n".join([*lines, ""])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=CORPUS / "manifest.yaml")
    parser.add_argument("--check-manifest", action="store_true")
    parser.add_argument("--intents", type=Path, default=CORPUS / "hypotheses.jsonl")
    parser.add_argument("--labels", type=Path, default=CORPUS / "labels.csv")
    parser.add_argument("--second", type=Path)
    parser.add_argument("--output", type=Path, default=CORPUS.parent / "reports" / "coverage.md")
    args = parser.parse_args()
    try:
        manifest = read_manifest(args.manifest)
        errors = validate_manifest(manifest)
        if errors:
            raise CorpusError("manifest validation failed:\n- " + "\n- ".join(errors))
        if args.check_manifest:
            print(f"Manifest validation passed: {args.manifest}")
            return 0
        intents = read_intents(args.intents, manifest)
        labels = read_labels(args.labels, intents, manifest.candidates, complete=True)
        second_path = args.second or (
            CORPUS / "labels_second.csv" if args.intents == CORPUS / "hypotheses.jsonl" else None
        )
        second = read_labels(second_path, intents, manifest.candidates, complete=False) if second_path else {}
        report = render_report(manifest, intents, labels, second)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(report)
        print(f"Coverage report written: {args.output}")
    except (OSError, CorpusError) as exc:
        print(f"Coverage calculation failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
