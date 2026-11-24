"""Build a CSV and summary from Loki ``logcli --output=jsonl`` output."""

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

FIELDS = ("input", "output", "cache_read", "cache_write")


def read_summaries(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: dict[str, dict[str, Any]] = {}
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError
            entry = item.get("line", item)
            if isinstance(entry, str):
                entry = json.loads(entry)
            if not isinstance(entry, dict) or entry.get("event") != "part.summary":
                raise ValueError
            if not isinstance(entry.get("part_id"), str) or not isinstance(entry.get("document_id"), str):
                raise ValueError
            if not isinstance(entry.get("duration_s"), (int, float)) or "cost_usd" not in entry:
                raise ValueError
            if entry["cost_usd"] is not None and not isinstance(entry["cost_usd"], (int, float)):
                raise ValueError
            if not isinstance(entry.get("usage"), dict) or not isinstance(entry.get("stage_durations", {}), dict):
                raise ValueError
            if any(not isinstance(v, dict) for v in entry["usage"].values()):
                raise ValueError
            if any(not isinstance(v.get(field, 0), (int, float)) for v in entry["usage"].values() for field in FIELDS):
                raise ValueError
            if entry["part_id"] in rows:
                skipped += 1
                continue
            rows[entry["part_id"]] = entry
        except (ValueError, TypeError, json.JSONDecodeError):
            skipped += 1
    return list(rows.values()), skipped


def write_report(rows: list[dict[str, Any]], output: Path, skipped: int = 0) -> dict[str, Any]:
    purposes = sorted({p for row in rows for p in row["usage"]})
    stages = sorted({s for row in rows for s in row.get("stage_durations", {})})
    columns = ["document_id", "part_id", "duration_s", "cost_usd"]
    columns += [f"tokens_{field}" for field in FIELDS]
    columns += [f"tokens_{purpose}_{field}" for purpose in purposes for field in FIELDS]
    columns += [f"stage_{stage}_seconds" for stage in stages]
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            flat = {key: row.get(key) for key in columns[:4]}
            for field in FIELDS:
                flat[f"tokens_{field}"] = sum(v.get(field, 0) for v in row["usage"].values())
                for purpose in purposes:
                    flat[f"tokens_{purpose}_{field}"] = row["usage"].get(purpose, {}).get(field, 0)
            for stage in stages:
                flat[f"stage_{stage}_seconds"] = row.get("stage_durations", {}).get(stage, 0)
            writer.writerow(flat)
    durations = [float(row["duration_s"]) for row in rows]
    costs = [float(row["cost_usd"]) for row in rows if row["cost_usd"] is not None]
    usage = [v for row in rows for v in row["usage"].values()]
    cache = sum(v.get("cache_read", 0) for v in usage)
    total = sum(v.get("input", 0) + v.get("cache_read", 0) + v.get("cache_write", 0) for v in usage)
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
