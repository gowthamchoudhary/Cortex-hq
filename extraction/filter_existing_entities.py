"""Filter noisy entities from an existing batch extraction output."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from extraction.extract import filter_candidate_entities  # noqa: E402


INPUT_PATH = PROJECT_ROOT / "eval" / "results" / "batch_extraction_output.json"
OUTPUT_PATH = PROJECT_ROOT / "eval" / "results" / "batch_extraction_output_filtered.json"


def filter_existing_entities(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> tuple[int, int]:
    payload: dict[str, Any] = json.loads(input_path.read_text(encoding="utf-8"))
    before_count = 0
    after_count = 0

    for result in payload.get("results", []):
        extraction = result.get("extraction") or {}
        entities = extraction.get("candidate_entities") or []
        before_count += len(entities)
        extraction["candidate_entities"] = filter_candidate_entities(extraction)
        after_count += len(extraction["candidate_entities"])

    summary = payload.get("summary")
    if isinstance(summary, dict):
        summary["total_entities"] = after_count

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return before_count, after_count


def main() -> None:
    before_count, after_count = filter_existing_entities()
    print(f"Entities before filtering: {before_count}")
    print(f"Entities after filtering: {after_count}")


if __name__ == "__main__":
    main()