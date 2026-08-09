"""Run the phase 3 compression benchmark over all observation fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.observation.compressor import ObservationCompressor  # noqa: E402
from app.observation.models import Observation  # noqa: E402


def main() -> int:
    fixture_dir = REPOSITORY_ROOT / "backend" / "tests" / "fixtures" / "observations"
    report_path = REPOSITORY_ROOT / "evaluation" / "reports" / "phase3_tree_compression.json"
    compressor = ObservationCompressor()
    cases: list[dict[str, object]] = []
    for fixture_path in sorted(fixture_dir.glob("*.json")):
        observation = Observation.model_validate_json(fixture_path.read_text(encoding="utf-8"))
        result = compressor.compress(observation)
        cases.append(
            {
                "fixture": fixture_path.name,
                "stats": result.stats.model_dump(),
            }
        )

    report = {
        "phase": 3,
        "description": "Raw deterministic Accessibility observation compression results",
        "compression_ratio_definition": "compressed_node_count / raw_node_count; lower means more removal",
        "cases": cases,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

