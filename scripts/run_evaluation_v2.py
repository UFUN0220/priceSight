"""Run all Evaluation v2 samples and write JSON + Markdown reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.runner import DEFAULT_DATASET, evaluate_dataset, markdown_report  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Replay PriceSight Evaluation v2")
    parser.add_argument("--sample-id", action="append", help="replay only one or more sample IDs")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json-report", type=Path, default=ROOT / "evaluation/reports/evaluation_v2.json")
    parser.add_argument("--markdown-report", type=Path, default=ROOT / "evaluation/reports/evaluation_v2.md")
    args = parser.parse_args()

    report = evaluate_dataset(args.dataset, set(args.sample_id) if args.sample_id else None)
    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_report.write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
