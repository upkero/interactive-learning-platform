import json
from collections import Counter
from pathlib import Path
from uuid import UUID

import pytest

from evals import embeddings_benchmark as benchmark
from src.app.contracts.solver.widget_candidate import WidgetMatch

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
    assert Counter((item.split, item.language) for item in corpus.intents if item.widget_id) == {
        ("calibration", "en"): 50,
        ("calibration", "ru"): 25,
        ("test", "en"): 50,
        ("test", "ru"): 25,
    }
    assert all(widget.language == "en" and len(widget.descriptions) == 4 for widget in corpus.widgets)
    assert {item.widget_id for item in corpus.intents if item.widget_id} == {item.widget_id for item in corpus.widgets}


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
