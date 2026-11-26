"""Run the five reference sources through the configured real main-pass model.

This command makes paid API calls. Run deliberately with Anthropic configured:
    python -m evals.main_pass_live OUTPUT_DIRECTORY

The output directory must be empty. It will contain individual snapshots and
a summary; failed cases are reported, never replaced with fabricated drafts.
"""

import argparse
import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from evals.term_check import check_reference_parts, missing_terms
from src.app.contracts.documents.topic_node import TopicNode
from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse
from src.app.contracts.solver.main_pass import MainPassInput, ReaderProfile
from src.app.core.settings.llm import get_llm_settings
from src.app.core.settings.solver import SolverSettings
from src.app.exceptions.llm import LLMSchemaError
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.factory import create_llm_client
from src.app.observability.noop_metrics_collector import NoopMetricsCollector
from src.app.services.solver.main_pass.directive_parser import check_draft
from src.app.services.solver.main_pass.directives import PageDraft
from src.app.services.solver.main_pass.main_pass import MainPassService
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.widgets import FakePrimitiveRepository
from tests.support.fixtures.main_pass import build_input, build_primitives

_FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "support" / "fixtures" / "main_pass"


@dataclass(frozen=True)
class Case:
    id: str
    payload: MainPassInput
    glossary: list[str]


class FirstAnswerMetrics(NoopMetricsCollector):
    """Record the service's first schema-valid draft classification."""

    def __init__(self) -> None:
        self.answers: list[str] = []

    def increment_counter(self, name: str, *, labels: Mapping[str, str] | None = None, by: int = 1) -> None:
        if name == "main_pass.drafts_total" and labels is not None:
            self.answers.extend([labels["first_answer"]] * by)


class FirstDraftRecorder(LLMClient):
    """Capture a schema-valid draft and schema failures before it, per part."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.reset()

    def reset(self) -> None:
        self.first_draft: PageDraft | None = None
        self.schema_errors_before_first = 0
        self.schema_retry = False

    @property
    def model_name(self) -> str:
        return self.inner.model_name

    @property
    def provider_name(self) -> str:
        return self.inner.provider_name

    async def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        return await self.inner.complete(messages)

    async def complete_structured[T: BaseModel](self, request: LLMRequest, schema: type[T]) -> StructuredResponse[T]:
        if self.first_draft is None and self.schema_errors_before_first:
            self.schema_retry = True
        try:
            response = await self.inner.complete_structured(request, schema)
        except LLMSchemaError:
            if self.first_draft is None:
                self.schema_errors_before_first += 1
            raise
        if self.first_draft is None and isinstance(response.value, PageDraft):
            self.first_draft = response.value
        return response

    async def ping(self) -> bool:
        return await self.inner.ping()

    async def close(self) -> None:
        await self.inner.close()


def classify_first_draft(draft: PageDraft, payload: MainPassInput, settings: SolverSettings) -> dict[str, list[str]]:
    def check(alternation: bool) -> list[str]:
        return check_draft(
            draft.markdown,
            draft.directives,
            image_aliases={image.alias for image in payload.images},
            max_widgets=settings.max_widgets_per_part,
            max_quizzes=settings.max_quizzes_per_part,
            key_terms=draft.key_terms,
            alternation=alternation,
        )

    other = check(False)
    all_issues = check(True)
    return {"alternation": [issue for issue in all_issues if issue not in other], "other": other}


def load_cases(root: Path = _FIXTURES) -> list[Case]:
    document = json.loads((root / "document.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "reference_corpus" / "manifest.json").read_text(encoding="utf-8"))
    cases: list[Case] = []
    for part in document["parts"]:
        # Keep the two source parts and their common document context independent.
        payload = build_input(part["key"])
        payload = replace(payload, part_markdown=(root / part["markdown"]).read_text(encoding="utf-8"))
        cases.append(Case(part["key"], payload, part["glossary"]))
    for row in manifest["cases"]:
        text = (root / "reference_corpus" / row["source"]).read_text(encoding="utf-8")
        title = next(
            (line.removeprefix("## ").strip() for line in text.splitlines() if line.startswith("## ")), row["id"]
        )
        topic = TopicNode(id="1", title=title, level=1, start=0, end=len(text), own_tokens=0, total_tokens=0)
        payload = MainPassInput(
            document_id=uuid5(NAMESPACE_URL, f"main-pass-reference/{row['id']}"),
            part_id=uuid5(NAMESPACE_URL, f"main-pass-reference/{row['id']}/part"),
            document_title=title,
            outline=(topic,),
            part_title=title,
            part_markdown=text,
            part_topics=(title,),
            profile=ReaderProfile(level="novice", goal="understand", depth="standard"),
        )
        cases.append(Case(row["id"], payload, row["glossary"]))
    if len(cases) != 5 or len({case.id for case in cases}) != 5:
        raise ValueError("Expected five distinct reference cases.")
    for case in cases:
        if not case.glossary or missing_terms(case.payload.part_markdown, case.glossary):
            raise ValueError(f"{case.id}: glossary must be non-empty and present in the source")
    return cases


def _prepare_outputs(outputs: Path) -> None:
    outputs.mkdir(parents=True, exist_ok=True)
    if any(outputs.iterdir()):
        raise ValueError(f"Output directory must be empty: {outputs}")


def _prompt_version() -> str:
    prompt_path = (
        Path(__file__).resolve().parents[1] / "src" / "app" / "services" / "solver" / "main_pass" / "prompts.py"
    )
    return "sha256:" + hashlib.sha256(prompt_path.read_bytes()).hexdigest()


async def run_cases(
    cases: list[Case],
    service: MainPassService,
    metrics: FirstAnswerMetrics,
    recorder: FirstDraftRecorder,
    outputs: Path,
    *,
    model: str,
    prompt_version: str,
    settings: SolverSettings,
) -> dict[str, Any]:
    _prepare_outputs(outputs)
    failures: dict[str, str] = {}
    schema_retry_cases = 0
    alternation_violations = 0
    recorded_first_answers = 0
    for case in cases:
        recorder.reset()
        before = len(metrics.answers)
        try:
            result = await service.run(case.payload)
            if len(metrics.answers) != before + 1 or recorder.first_draft is None:
                raise RuntimeError("Service did not record exactly one first-answer classification")
            issues = classify_first_draft(recorder.first_draft, case.payload, settings)
            snapshot = {
                "model": model,
                "prompt_version": prompt_version,
                "generated_at": datetime.now(UTC).isoformat(),
                "first_answer": metrics.answers[-1],
                "first_schema_valid_draft": recorder.first_draft.model_dump(mode="json"),
                "first_answer_issues": issues,
                "schema_errors_before_first": recorder.schema_errors_before_first,
                "draft": asdict(result.draft),
            }
            (outputs / f"{case.id}.json").write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        except Exception as exc:
            failures[case.id] = type(exc).__name__
        finally:
            schema_retry_cases += int(recorder.schema_retry)
            if recorder.first_draft is not None:
                recorded_first_answers += 1
                issues = classify_first_draft(recorder.first_draft, case.payload, settings)
                alternation_violations += int(bool(issues["alternation"]))
                if case.id in failures:
                    partial = {
                        "model": model,
                        "prompt_version": prompt_version,
                        "generated_at": datetime.now(UTC).isoformat(),
                        "first_schema_valid_draft": recorder.first_draft.model_dump(mode="json"),
                        "first_answer_issues": issues,
                        "schema_errors_before_first": recorder.schema_errors_before_first,
                    }
                    (outputs / f"{case.id}.first.json").write_text(
                        json.dumps(partial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                    )
    violations = metrics.answers.count("violations")
    summary = {
        "cases": len(cases),
        "completed": len(cases) - len(failures),
        "failures": failures,
        "first_schema_valid_answers": len(metrics.answers),
        "first_answer_violations": violations,
        "first_answer_violation_fraction": violations / len(metrics.answers) if metrics.answers else None,
        "schema_retry_cases_before_first": schema_retry_cases,
        "schema_retry_case_fraction": schema_retry_cases / len(cases) if cases else None,
        "first_drafts_recorded": recorded_first_answers,
        "first_answer_alternation_violations": alternation_violations,
        "first_answer_alternation_fraction": (
            alternation_violations / recorded_first_answers if recorded_first_answers else None
        ),
    }
    (outputs / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


async def _run(outputs: Path) -> int:
    settings = get_llm_settings()
    if settings.provider != "anthropic" or settings.api_key is None:
        raise ValueError("Configure LLM_PROVIDER=anthropic and LLM_API_KEY before running the paid evaluation.")
    cases = load_cases()
    repo = FakePrimitiveRepository()
    for primitive in build_primitives():
        await repo.upsert(
            primitive_id=primitive.id,
            version=primitive.version,
            description=primitive.description,
            modes=primitive.modes,
            params_schema=primitive.params_schema,
        )
    metrics = FirstAnswerMetrics()
    client = FirstDraftRecorder(create_llm_client(settings))
    solver_settings = SolverSettings()
    service = MainPassService(
        llm=client,
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        primitives=lambda _: repo,
        settings=solver_settings,
        metrics=metrics,
    )
    prompt_version = _prompt_version()
    try:
        summary = await run_cases(
            cases,
            service,
            metrics,
            client,
            outputs,
            model=settings.model,
            prompt_version=prompt_version,
            settings=solver_settings,
        )
    finally:
        await client.close()
    problems = check_reference_parts(outputs=outputs)
    print(json.dumps({"summary": summary, "term_problem_count": len(problems)}, ensure_ascii=False, indent=2))
    return int(bool(summary["failures"] or problems))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outputs", type=Path, help="Empty directory for recorded outputs")
    return asyncio.run(_run(parser.parse_args().outputs))


if __name__ == "__main__":
    raise SystemExit(main())
