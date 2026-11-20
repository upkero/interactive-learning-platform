"""Behavioural tests for hypothetical coverage and corpus validation."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from evals.coverage import (
    agreement,
    coverage,
    greedy,
    read_intents,
    read_labels,
    read_manifest,
    render_report,
    sample_ids,
    validate_manifest,
)

pytestmark = pytest.mark.unit


def test_metrics_exclude_not_needed_and_keep_other_in_denominator() -> None:
    labels = {
        "a": {"candidate": "array-ops", "fit": "full"},
        "b": {"candidate": "array-ops", "fit": "extend"},
        "c": {"candidate": "other:table", "fit": "no"},
        "d": {"candidate": "not_needed", "fit": "no"},
    }
    intents = {
        "a": {"discipline": "algorithms"},
        "b": {"discipline": "algorithms"},
        "c": {"discipline": "databases"},
        "d": {"discipline": "networks"},
    }
    result = coverage(labels, {"array-ops"}, intents)
    assert result["total"] == 3
    assert result["cov"] == pytest.approx(1 / 3)
    assert result["cov_plus"] == pytest.approx(2 / 3)
    assert result["cov_d"] == {"algorithms": 1.0, "databases": 0.0, "networks": None, "os": None}


def test_greedy_ties_use_effort_then_id_and_stop_at_zero_gain() -> None:
    candidates = {"zeta": {"effort": "M"}, "alpha": {"effort": "S"}, "beta": {"effort": "S"}, "unused": {"effort": "S"}}
    labels = {name: {"candidate": name, "fit": "full"} for name in ("zeta", "alpha", "beta")}
    intents = {name: {"discipline": "networks"} for name in labels}
    steps = greedy(labels, intents, candidates)
    assert [name for name, _ in steps] == ["alpha", "beta", "zeta"]
    assert steps[-1][1]["cov_plus"] == 1.0


def test_sample_and_agreement_are_deterministic_and_validate_coverage() -> None:
    sample = sample_ids([str(i) for i in range(40)])
    assert len(sample) == 8
    assert sample == sample_ids(list(reversed([str(i) for i in range(40)])))
    primary = {key: {"candidate": "a"} for key in sample}
    secondary = {key: {"candidate": "a" if index else "b"} for index, key in enumerate(sample)}
    assert agreement(primary, secondary, sample) == 7 / 8
    assert agreement(primary, {}, sample) is None
    with pytest.raises(ValueError, match="exactly"):
        agreement(primary, {sample[0]: {"candidate": "a"}}, sample)


def test_manifest_detects_missing_paths_and_language_rules(tmp_path: Path) -> None:
    chapters = []
    for discipline in ("networks", "os", "algorithms", "databases"):
        for index in range(5):
            name = f"{discipline}-{index}.md"
            (tmp_path / name).write_text("# Chapter\n", encoding="utf-8")
            chapters.append(
                {
                    "id": name,
                    "discipline": discipline,
                    "lang": "en" if index < 3 else "ru",
                    "title": name,
                    "author": "Author",
                    "license": "CC BY 4.0",
                    "source": "https://example.org",
                    "path": name,
                }
            )
    manifest = {"chapters": chapters, "candidates": {"a": {"effort": "S", "summary": "A"}}}
    path = tmp_path / "manifest.yaml"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_manifest(path) == []
    chapters[2]["sha256"] = hashlib.sha256(b"different").hexdigest()
    (tmp_path / chapters[0]["path"]).unlink()
    chapters[1]["lang"] = "de"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    errors = validate_manifest(path)
    assert any("missing or unsafe" in error for error in errors)
    assert any("unsupported language" in error for error in errors)
    assert any("sha256 does not match" in error for error in errors)


def test_intents_must_reference_actual_text_and_labels_must_be_complete(tmp_path: Path) -> None:
    (tmp_path / "chapter.md").write_text("# Real heading\n", encoding="utf-8")
    manifest = {"chapters": [{"id": "c", "discipline": "networks", "path": "chapter.md"}]}
    row = {
        "intent_id": "i",
        "chapter_id": "c",
        "description": "Visualize",
        "source_quote": "Real heading",
        "source_line": "1",
        "provenance": "hypothetical",
    }
    source = tmp_path / "hypotheses.jsonl"
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    intents = read_intents(source, manifest, tmp_path)
    target = tmp_path / "labels.csv"
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["intent_id", "candidate", "fit", "note"])
        writer.writerow(["i", "array-ops", "full", ""])
    assert read_labels(target, intents, {"array-ops": {}}, complete=True)["i"]["fit"] == "full"
    target.write_text("intent_id,candidate,fit,note\ni,array-ops\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete CSV row"):
        read_labels(target, intents, {"array-ops": {}}, complete=True)
    row["source_quote"] = "Not present"
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source_quote not found"):
        read_intents(source, manifest, tmp_path)


def test_committed_corpus_and_report_are_consistent() -> None:
    root = Path(__file__).resolve().parents[2] / "evals"
    corpus = root / "corpus"
    path = corpus / "manifest.yaml"
    assert validate_manifest(path) == []
    manifest = read_manifest(path)
    intents = read_intents(corpus / "hypotheses.jsonl", manifest, corpus)
    primary = read_labels(corpus / "labels.csv", intents, manifest["candidates"], complete=True)
    secondary = read_labels(corpus / "labels_second.csv", intents, manifest["candidates"], complete=False)
    assert (root / "reports" / "coverage.md").read_text(encoding="utf-8") == render_report(
        manifest, intents, primary, secondary
    )
