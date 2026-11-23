"""Build a CSV and summary from Loki ``logcli --output=jsonl`` output."""

import argparse
import csv
import json
import statistics
from pathlib import Path


def read_summaries(path: Path) -> list[dict[str, object]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        entry = item.get("line", item)
        if isinstance(entry, str):
            entry = json.loads(entry)
        if entry.get("event") == "part.summary":
            rows.append(entry)
    return rows


def write_report(rows: list[dict[str, object]], output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["document_id", "part_id", "duration_s", "cost_usd", "usage"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
    durations = [float(row["duration_s"]) for row in rows]
    costs = [float(row["cost_usd"]) for row in rows]
    cache = sum(sum(values.get("cache_read", 0) for values in row.get("usage", {}).values()) for row in rows)
    total = sum(
        sum(values.get("input", 0) + values.get("cache_read", 0) for values in row.get("usage", {}).values())
        for row in rows
    )
    print(
        json.dumps(
            {
                "parts": len(rows),
                "duration_median": statistics.median(durations) if durations else 0,
                "duration_p95": _percentile(durations, 0.95),
                "cost_median": statistics.median(costs) if costs else 0,
                "cache_share": cache / total if total else 0,
            },
            indent=2,
        )
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * percentile))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    write_report(read_summaries(args.input), args.output)


if __name__ == "__main__":
    main()
