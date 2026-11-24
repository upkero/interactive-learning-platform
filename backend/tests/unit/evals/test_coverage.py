"""Boundary and behaviour tests for the corpus and coverage calculator."""

import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
import yaml

from evals.coverage import (
    CORPUS,
    Candidate,
    Chapter,
    CorpusError,
    Discipline,
    Intent,
    IntentSet,
    Label,
    Manifest,
    agreement,
    coverage,
    greedy,
    read_intents,
    read_labels,
    read_manifest,
    render_report,
    sample_ids,
    top_other,
    validate_manifest,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    (tmp_path / "chapter.md").write_text("# Real text\n")
    chapters = tuple(
        Chapter(
            f"{d}-{i}",
            cast(Discipline, d),
            "en" if n < 8 else "ru",
            "Title",
            "chapter.md",
            "Конспект кафедры",
            "CC BY 4.0",
        )
        for n, (d, i) in enumerate((d, i) for d in ("networks", "os", "algorithms", "databases") for i in range(5))
    )
    return Manifest(chapters, {"array-ops": Candidate("M", "Array")}, tmp_path)


@pytest.mark.parametrize(("size", "ok"), [(19, False), (20, True), (30, True), (31, False)])
def test_chapter_count_boundaries(manifest: Manifest, size: int, ok: bool) -> None:
    chapters = list(manifest.chapters)
    while len(chapters) < size:
        chapters.append(replace(chapters[0], id=f"extra-{len(chapters)}", lang="en"))
    result = validate_manifest(replace(manifest, chapters=tuple(chapters[:size])))
    assert (not any("chapter count" in e for e in result)) == ok


def test_discipline_minimum_and_english_threshold(manifest: Manifest) -> None:
    assert not validate_manifest(manifest)
    chapters = tuple(c for c in manifest.chapters if c.id != "os-0")
    assert any("os: need at least 5" in x for x in validate_manifest(replace(manifest, chapters=chapters)))
    # 21 chapters allow exactly 7/21 English; one fewer fails.
    chapters_list = [*manifest.chapters, replace(manifest.chapters[0], id="extra")]
    chapters_list = [replace(c, lang="en" if i < 7 else "ru") for i, c in enumerate(chapters_list)]
    assert not any("English" in e for e in validate_manifest(replace(manifest, chapters=tuple(chapters_list))))
    chapters_list[0] = replace(chapters_list[0], lang="ru")
    assert any("English" in e for e in validate_manifest(replace(manifest, chapters=tuple(chapters_list))))


def test_duplicate_private_paths_and_missing(manifest: Manifest) -> None:
    chapters = list(manifest.chapters)
    chapters[1] = replace(chapters[1], id=chapters[0].id, license="private", path="missing.md")
    errors = validate_manifest(replace(manifest, chapters=tuple(chapters)))
    assert any("duplicate" in e for e in errors)
    assert any("private license" in e for e in errors)
    assert any("missing or unsafe" in e for e in errors)


def test_yaml_manifest_and_optional_author(manifest: Manifest, tmp_path: Path) -> None:
    data = {
        "candidates": {"array-ops": {"effort": "M", "summary": "Array"}},
        "chapters": [
            {
                "id": c.id,
                "discipline": c.discipline,
                "lang": c.lang,
                "title": c.title,
                "path": c.path,
                "source": c.source,
                "license": c.license,
            }
            for c in manifest.chapters
        ],
    }
    path = tmp_path / "manifest.yaml"
    path.write_text("# actual YAML\n" + yaml.safe_dump(data, allow_unicode=True))
    assert not validate_manifest(read_manifest(path))


def intent_set(ids: list[str]) -> IntentSet:
    return IntentSet(
        {i: Intent(i, "ch", "networks", "intent", "span", "main_pass") for i in ids}, "main_pass", "abc", "model"
    )


def test_coverage_and_other_greedy() -> None:
    intents = intent_set(["a", "b", "c", "d"])
    labels = {
        "a": Label("a", "array-ops", "full"),
        "b": Label("b", "other:table", "extend", "table"),
        "c": Label("c", "other:table", "full", "table"),
        "d": Label("d", "not_needed", "no", "not needed"),
    }
    stats = coverage(labels, {"array-ops"}, intents)
    assert stats.cov == pytest.approx(1 / 3) and stats.cov_plus == pytest.approx(1 / 3)
    assert stats.cov_d["networks"] == pytest.approx(1 / 3)
    assert greedy(labels, intents, {"array-ops": Candidate("S", "array")})[0].candidate == "other:table"


def test_greedy_limit_and_top_five() -> None:
    ids = [str(i) for i in range(28)]
    intents = intent_set(ids)
    labels = {}
    n = 0
    for index in range(7):
        for _ in range(index + 1):
            iid = ids[n]
            n += 1
            labels[iid] = Label(iid, f"other:c{index}", "full", "new")
    assert len(greedy(labels, intents, {})) == 6
    assert top_other(labels) == [("other:c6", 7), ("other:c5", 6), ("other:c4", 5), ("other:c3", 4), ("other:c2", 3)]


def test_labels_bom_validation_and_completeness(tmp_path: Path) -> None:
    intents = intent_set(["a", "b"])
    path = tmp_path / "labels.csv"
    candidates = {"array-ops": Candidate("S", "a")}

    def write(rows: list[list[str]]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["intent_id", "candidate", "fit", "note"])
            writer.writerows(rows)

    write([["a", "array-ops", "full", ""], ["b", "array-ops", "full", ""]])
    assert len(read_labels(path, intents, candidates, complete=True)) == 2
    for rows in ([["a", "array-ops", "extend", ""]], [["a", "other:x", "full", ""]], [["a", "unknown", "full", ""]]):
        write(rows)
        with pytest.raises(CorpusError):
            read_labels(path, intents, candidates, complete=False)
    write([["a", "array-ops", "full", ""]])
    with pytest.raises(CorpusError, match="incomplete"):
        read_labels(path, intents, candidates, complete=True)


def test_mainpass_jsonl_header_and_report(tmp_path: Path) -> None:
    (tmp_path / "c.md").write_text("source text")
    manifest = Manifest(
        (Chapter("c", "networks", "en", "c", "c.md", "source", "private"),),
        {"array-ops": Candidate("M", "array")},
        tmp_path,
    )
    path = tmp_path / "intents.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(x)
            for x in [
                {"prompt_sha": "abc", "model": "example"},
                {"intent_id": "i1", "chapter_id": "c", "intent": "show one", "source_span": "source text"},
                {"intent_id": "i2", "chapter_id": "c", "intent": "show two", "source_span": "source text"},
            ]
        )
    )
    intents = read_intents(path, manifest)
    labels = {i: Label(i, "array-ops", "full") for i in intents.items}
    report = render_report(manifest, intents, labels, {})
    assert "abc" in report and "example" in report and "искусствен" not in report
    assert sample_ids([str(i) for i in range(40)]) == sample_ids([str(i) for i in reversed(range(40))])
    assert agreement({"i1": labels["i1"]}, {"i1": labels["i1"]}, ["i1"]) == 1


def test_repository_corpus_and_report() -> None:
    manifest = read_manifest(CORPUS / "manifest.yaml")
    assert not validate_manifest(manifest)
    intents = read_intents(CORPUS / "hypotheses.jsonl", manifest)
    labels = read_labels(CORPUS / "labels.csv", intents, manifest.candidates, complete=True)
    secondary = read_labels(CORPUS / "labels_second.csv", intents, manifest.candidates, complete=False)
    assert (CORPUS.parent / "reports/coverage.md").read_text() == render_report(manifest, intents, labels, secondary)
