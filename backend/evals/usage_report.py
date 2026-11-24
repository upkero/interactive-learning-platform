"""Build a CSV and summary from Loki ``logcli --output=jsonl`` output."""

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

FIELDS = ("input", "output", "cache_read", "cache_write")


@dataclass(frozen=True, slots=True)
class TokenCounts:
    input: int
    output: int
    cache_read: int
    cache_write: int


@dataclass(frozen=True, slots=True)
class ReportRow:
    document_id: str
    part_id: str
    duration_s: float
    cost_usd: float | None
    usage: dict[str, TokenCounts]
    stage_durations: dict[str, float]


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a finite non-negative number")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError("expected a finite non-negative number") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("expected a finite non-negative number")
    return number


def _tokens(value: object) -> TokenCounts:
    if not isinstance(value, dict):
        raise ValueError("invalid token counts")
    numbers: list[int] = []
    for field in FIELDS:
        item: object = value.get(field, 0)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ValueError("invalid token count")
        numbers.append(item)
    return TokenCounts(*numbers)


def _parse(entry: object) -> ReportRow:
    if not isinstance(entry, dict) or entry.get("event") != "part.summary":
        raise ValueError("not a part summary")
    document_id: object = entry.get("document_id")
    part_id: object = entry.get("part_id")
    if not isinstance(document_id, str) or not isinstance(part_id, str) or "cost_usd" not in entry:
        raise ValueError("missing identifiers or cost")
    cost: object = entry["cost_usd"]
    usage: object = entry.get("usage")
    stages: object = entry.get("stage_durations", {})
    if not isinstance(usage, dict) or not isinstance(stages, dict):
        raise ValueError("invalid usage or stage durations")
    if any(not isinstance(k, str) for k in usage) or any(not isinstance(k, str) for k in stages):
        raise ValueError("invalid usage or stage name")
    return ReportRow(
        document_id=document_id,
        part_id=part_id,
        duration_s=_number(entry.get("duration_s")),
        cost_usd=None if cost is None else _number(cost),
        usage={k: _tokens(v) for k, v in usage.items()},
        stage_durations={k: _number(v) for k, v in stages.items()},
    )


def read_summaries(path: Path) -> tuple[list[ReportRow], int]:
    rows: dict[str, ReportRow] = {}
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item: object = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("invalid log entry")
            entry: object = item.get("line", item)
            if isinstance(entry, str):
                entry = json.loads(entry)
            row = _parse(entry)
            if row.part_id in rows:
                skipped += 1
                continue
            rows[row.part_id] = row
        except (ValueError, TypeError):
            skipped += 1
    return list(rows.values()), skipped


def write_report(rows: list[ReportRow], output: Path, skipped: int = 0) -> dict[str, int | float | str | None]:
    purposes = sorted({p for row in rows for p in row.usage})
    stages = sorted({s for row in rows for s in row.stage_durations})
    columns = ["document_id", "part_id", "duration_s", "cost_usd"]
    columns += [f"tokens_{field}" for field in FIELDS]
    columns += [f"tokens_{purpose}_{field}" for purpose in purposes for field in FIELDS]
    columns += [f"stage_{stage}_seconds" for stage in stages]
    empty = TokenCounts(0, 0, 0, 0)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            flat: dict[str, str | int | float | None] = {
                "document_id": row.document_id,
                "part_id": row.part_id,
                "duration_s": row.duration_s,
                "cost_usd": row.cost_usd,
            }
            for field in FIELDS:
                flat[f"tokens_{field}"] = sum(getattr(v, field) for v in row.usage.values())
                for purpose in purposes:
                    flat[f"tokens_{purpose}_{field}"] = getattr(row.usage.get(purpose, empty), field)
            for stage in stages:
                flat[f"stage_{stage}_seconds"] = row.stage_durations.get(stage, 0)
            writer.writerow(flat)
    durations = [row.duration_s for row in rows]
    costs = [row.cost_usd for row in rows if row.cost_usd is not None]
    usage = [v for row in rows for v in row.usage.values()]
    cache = sum(v.cache_read for v in usage)
    total = sum(v.input + v.cache_read + v.cache_write for v in usage)
    return {
        "parts": len(rows),
        "skipped": skipped,
        "unknown_cost_parts": len(rows) - len(costs),
        "duration_median": statistics.median(durations) if durations else None,
        "duration_p95": _percentile(durations, 0.95),
        "cost_median": statistics.median(costs) if costs else None,
        "cost_p95": _percentile(costs, 0.95),
        "cache_share": cache / total if total else 0,
        "cache_share_definition": "cache_read / (input + cache_read + cache_write)",
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    return sorted(values)[math.ceil(len(values) * percentile) - 1] if values else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, skipped = read_summaries(args.input)
    print(json.dumps(write_report(rows, args.output, skipped), indent=2))


if __name__ == "__main__":
    main()
