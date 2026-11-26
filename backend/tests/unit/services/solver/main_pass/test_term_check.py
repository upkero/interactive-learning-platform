"""The evaluator requires complete source data and recorded model outputs."""

import json
from pathlib import Path

from evals.term_check import check_reference_parts, main


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _corpus(root: Path) -> Path:
    corpus = root / "reference_corpus"
    outputs = corpus / "outputs"
    outputs.mkdir(parents=True)
    parts = [{"key": f"p{i}", "markdown": f"p{i}.md", "glossary": [f"Term{i}"]} for i in range(2)]
    cases = [{"id": f"c{i}", "source": f"c{i}.md", "glossary": [f"Term{i + 2}"]} for i in range(3)]
    _write(root / "document.json", {"parts": parts})
    _write(corpus / "manifest.json", {"cases": cases})
    for i, case_id in enumerate(("p0", "p1", "c0", "c1", "c2")):
        source = root if i < 2 else corpus
        (source / f"{case_id}.md").write_text(f"Term{i}", encoding="utf-8")
        _write(
            outputs / f"{case_id}.json",
            {
                "model": "test model",
                "prompt_version": "test",
                "generated_at": "test date",
                "draft": {"markdown": f"Term{i} Key{i}", "key_terms": [f"Key{i}"]},
            },
        )
    return outputs


def test_all_five_cases_and_snapshot_terms_are_checked(tmp_path: Path) -> None:
    outputs = _corpus(tmp_path)
    assert check_reference_parts(tmp_path, outputs) == []
    snapshot = json.loads((outputs / "c2.json").read_text(encoding="utf-8"))
    snapshot["draft"]["markdown"] = "term4"
    _write(outputs / "c2.json", snapshot)
    problems = check_reference_parts(tmp_path, outputs)
    assert any("c2: glossary missing from output: Term4" in problem for problem in problems)
    assert any("c2: key terms missing from output: Key4" in problem for problem in problems)


def test_missing_glossary_snapshot_and_provenance_fail(tmp_path: Path) -> None:
    outputs = _corpus(tmp_path)
    document = json.loads((tmp_path / "document.json").read_text(encoding="utf-8"))
    document["parts"][0].pop("glossary")
    _write(tmp_path / "document.json", document)
    (outputs / "c1.json").unlink()
    snapshot = json.loads((outputs / "p1.json").read_text(encoding="utf-8"))
    snapshot.pop("model")
    _write(outputs / "p1.json", snapshot)
    problems = check_reference_parts(tmp_path, outputs)
    assert any("p0: glossary must be" in problem for problem in problems)
    assert any("c1.json" in problem and "cannot read JSON" in problem for problem in problems)
    assert any("p1: snapshot requires non-empty model" in problem for problem in problems)


def test_real_reference_corpus_has_no_fabricated_outputs(tmp_path: Path) -> None:
    # An empty output directory must never be reported as a successful evaluation.
    assert main([str(tmp_path)]) == 1
