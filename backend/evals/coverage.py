"""Corpus manifest checks used by the coverage evaluation workflow."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ALLOWED_DISCIPLINES = frozenset({"networks", "os", "algorithms", "databases"})
ALLOWED_LANGUAGES = frozenset({"ru", "en"})


def validate_manifest(manifest_path: Path) -> list[str]:
    """Return all violations rather than stopping at the first malformed entry."""
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read valid YAML/JSON manifest: {exc}"]

    errors: list[str] = []
    chapters = data.get("chapters")
    if not isinstance(chapters, list):
        return ["chapters must be a list"]
    if not 20 <= len(chapters) <= 30:
        errors.append(f"chapter count must be 20..30, got {len(chapters)}")

    ids: set[str] = set()
    disciplines: Counter[str] = Counter()
    english = 0
    corpus_root = manifest_path.parent
    for index, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            errors.append(f"chapter #{index} must be an object")
            continue
        chapter_id = chapter.get("id")
        if not isinstance(chapter_id, str) or not chapter_id:
            errors.append(f"chapter #{index}: id is required")
        elif chapter_id in ids:
            errors.append(f"duplicate chapter id: {chapter_id}")
        else:
            ids.add(chapter_id)
        discipline = chapter.get("discipline")
        if discipline not in ALLOWED_DISCIPLINES:
            errors.append(f"{chapter_id or index}: unsupported discipline {discipline!r}")
        else:
            disciplines[discipline] += 1
        lang = chapter.get("lang")
        if lang not in ALLOWED_LANGUAGES:
            errors.append(f"{chapter_id or index}: unsupported language {lang!r}")
        elif lang == "en":
            english += 1
        path_value = chapter.get("path")
        if not isinstance(path_value, str) or not path_value:
            errors.append(f"{chapter_id or index}: path is required")
        else:
            path = (corpus_root / path_value).resolve()
            if corpus_root.resolve() not in path.parents or not path.is_file():
                errors.append(f"{chapter_id or index}: missing path {path_value}")
        if not isinstance(chapter.get("title"), str) or not chapter["title"].strip():
            errors.append(f"{chapter_id or index}: title is required")
        if not isinstance(chapter.get("source"), str) or not chapter["source"].startswith(("https://", "http://")):
            errors.append(f"{chapter_id or index}: source must be an HTTP(S) URL")
        license_name = chapter.get("license")
        if not isinstance(license_name, str) or not license_name.strip():
            errors.append(f"{chapter_id or index}: license is required")
        elif license_name == "private" and not str(path_value).startswith("private/"):
            errors.append(f"{chapter_id or index}: private license requires private/ path")

    for discipline in sorted(ALLOWED_DISCIPLINES):
        if disciplines[discipline] < 5:
            errors.append(f"{discipline}: need at least 5 chapters, got {disciplines[discipline]}")
    if len(chapters) and english * 3 < len(chapters):
        errors.append(f"English chapters must be at least one third, got {english}/{len(chapters)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("evals/corpus/manifest.yaml"))
    parser.add_argument("--check-manifest", action="store_true")
    args = parser.parse_args()
    errors = validate_manifest(args.manifest)
    if errors:
        print("Manifest validation failed:")
        print(*[f"- {error}" for error in errors], sep="\n")
        return 1
    print(f"Manifest validation passed: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
