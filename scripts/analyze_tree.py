"""Analyze one Accessibility observation fixture before and after compression."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.observation.compressor import ObservationCompressor  # noqa: E402
from app.observation.models import Observation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="Path to an observation JSON fixture")
    args = parser.parse_args()

    fixture = args.fixture.resolve()
    observation = Observation.model_validate_json(fixture.read_text(encoding="utf-8"))
    result = ObservationCompressor().compress(observation)
    print(
        json.dumps(
            {"fixture": str(fixture), "stats": result.stats.model_dump()},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

