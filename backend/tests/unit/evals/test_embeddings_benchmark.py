import json
from collections import Counter
from pathlib import Path
from uuid import UUID

import pytest

from evals import embeddings_benchmark as benchmark
from src.app.contracts.solver.widget_candidate import WidgetMatch
from src.app.core.settings.embeddings import get_embeddings_settings
from src.app.embeddings.bge_m3 import BGE_M3_REVISION

pytestmark = pytest.mark.unit


def test_committed_corpus_has_labels_and_no_split_leakage() -> None:
    corpus = benchmark.load_corpus(
        benchmark.DATA / "search_library.jsonl",
        benchmark.DATA / "search_intents.jsonl",
    )
    plan = benchmark._plan(corpus)

    assert plan["widgets"] == 60
    assert plan["descriptions"] == 240
    assert plan["labeled_intents"] == 150
    assert plan["cross_language_intents"] == 50
    assert plan["no_match_intents"] == 30
    assert plan["embedding_batches"] == 14
    assert plan["full_latency_batches"] == 13
    assert plan["revision"] == BGE_M3_REVISION
    assert Counter((item.split, item.language) for item in corpus.intents if item.widget_id) == {
        ("calibration", "en"): 50,
        ("calibration", "ru"): 25,
        ("test", "en"): 50,
        ("test", "ru"): 25,
    }
    assert all(widget.language == "en" and len(widget.descriptions) == 4 for widget in corpus.widgets)
    assert {item.widget_id for item in corpus.intents if item.widget_id} == {item.widget_id for item in corpus.widgets}


def test_corpus_fingerprint_is_independent_of_crlf_line_endings(tmp_path: Path) -> None:
    library_bytes = benchmark._canonical_jsonl_bytes((benchmark.DATA / "search_library.jsonl").read_bytes())
    intent_bytes = benchmark._canonical_jsonl_bytes((benchmark.DATA / "search_intents.jsonl").read_bytes())
    lf_library = tmp_path / "library-lf.jsonl"
    lf_intents = tmp_path / "intents-lf.jsonl"
    crlf_library = tmp_path / "library-crlf.jsonl"
    crlf_intents = tmp_path / "intents-crlf.jsonl"
    lf_library.write_bytes(library_bytes)
    lf_intents.write_bytes(intent_bytes)
    crlf_library.write_bytes(library_bytes.replace(b"\n", b"\r\n"))
    crlf_intents.write_bytes(intent_bytes.replace(b"\n", b"\r\n"))

    lf_corpus = benchmark.load_corpus(lf_library, lf_intents)
    crlf_corpus = benchmark.load_corpus(crlf_library, crlf_intents)

    assert lf_corpus.fingerprint == crlf_corpus.fingerprint
    assert lf_corpus.fingerprint == "1988d0dafeb81d97533dacedd0811054f226adff5d8a3aab165646bfd1d624a0"


def test_plan_cli_includes_the_configured_revision(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "bge_m3")
    monkeypatch.setenv("EMBEDDINGS_REVISION", revision)
    get_embeddings_settings.cache_clear()

    assert benchmark.main(["--plan"]) == 0

    plan = json.loads(capsys.readouterr().out)
    assert plan["revision"] == revision
    get_embeddings_settings.cache_clear()


def test_threshold_keeps_calibration_hits_and_scores_negatives() -> None:
    expected = UUID(int=1)
    distractor = UUID(int=2)
    rows = [
        benchmark.ScoredIntent(
            benchmark.Intent(intent="positive", widget_id=expected, language="en", split="calibration"),
            [WidgetMatch(distractor, "distractor", 0.3), WidgetMatch(expected, "expected", 0.51231)],
        ),
        benchmark.ScoredIntent(
            benchmark.Intent(intent="miss", widget_id=expected, language="en", split="calibration"),
            [WidgetMatch(distractor, "distractor", 0.6)],
        ),
        benchmark.ScoredIntent(
            benchmark.Intent(intent="out of library", widget_id=None, language="en", split="calibration"),
            [WidgetMatch(distractor, "distractor", 0.52)],
        ),
    ]

    assert benchmark._calibrate(rows[1:]) is None
    cutoff = benchmark._calibrate(rows)
    assert cutoff == 0.5124
    scores = benchmark._score(rows, cutoff)
    assert scores.recall_at_1 == 0.0
    assert scores.recall_at_5 == 0.5
    assert scores.mrr_at_5 == 0.25
    assert scores.negative_acceptance == 0.0
    assert benchmark._score(rows).negative_acceptance == 1.0


@pytest.mark.parametrize(("voyage_recall", "winner"), [(0.84, "bge_m3"), (0.85, "voyage"), (0.90, "voyage")])
def test_compare_uses_five_percentage_point_margin(tmp_path: Path, voyage_recall: float, winner: str) -> None:
    args = []
    for provider, recall in [("bge_m3", 0.80), ("voyage", voyage_recall)]:
        path = tmp_path / f"{provider}.json"
        path.write_text(
            json.dumps({"provider": provider, "corpus_sha256": "same", "test_unfiltered": {"recall_at_5": recall}}),
            encoding="utf-8",
        )
        args.append(path)
    assert benchmark._compare(args)["recommended_provider"] == winner
