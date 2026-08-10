"""Freeze a reproducible pre-change evaluation baseline.

The baseline is intentionally write-once.  It records the repository commit,
the test/coverage command output, frozen DEV/HOLDOUT scopes, human metrics,
and the existing Bad Case aggregation without changing annotations or labels.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "evaluation" / "results"
DATASET = ROOT / "evaluation" / "datasets" / "evaluation_v2.jsonl"
ANNOTATIONS = ROOT / "evaluation" / "datasets" / "human_annotations.jsonl"
SPLIT = ROOT / "evaluation" / "datasets" / "human_eval_split.json"


def _run_tests() -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--cov=backend/app",
        "--cov-branch",
        "--cov-report=term-missing",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    passed_match = re.search(r"(?P<count>\d+) passed", output)
    coverage_match = re.search(r"^TOTAL\s+\d+\s+\d+\s+\d+\s+(?P<coverage>\d+)%", output, re.MULTILINE)
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": int(passed_match.group("count")) if passed_match else None,
        "branch_coverage_percent": int(coverage_match.group("coverage")) if coverage_match else None,
        "output": output,
    }


def _metric(metrics: dict[str, Any], name: str) -> dict[str, Any]:
    value = metrics[name]
    return {
        "numerator": value["numerator"],
        "denominator": value["denominator"],
        "accuracy": value["accuracy"],
    }


def _scope_metrics(report: dict[str, Any]) -> dict[str, Any]:
    metrics = report["metrics_by_scope"]["ALL"]
    names = (
        "hybrid_exact_core_v1_accuracy",
        "hybrid_exact_strict_v2_accuracy",
        "hybrid_quantity_accuracy",
        "hybrid_specification_accuracy",
        "hybrid_displayed_price_accuracy",
        "hybrid_effective_price_accuracy",
        "hybrid_ambiguous_detection_accuracy",
    )
    return {name: _metric(metrics, name) for name in names}


def _build_report() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))
    from evaluation.runner import evaluate_dataset  # noqa: PLC0415

    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    scopes: dict[str, Any] = {}
    for name, ids in (
        ("DEV", set(split["dev_sample_ids"])),
        ("HOLDOUT", set(split["holdout_sample_ids"])),
        ("ALL", None),
    ):
        report = evaluate_dataset(DATASET, ids, ANNOTATIONS)
        scopes[name] = {
            "dataset_count": report["dataset_count"],
            "metrics": _scope_metrics(report),
        }

    full = evaluate_dataset(DATASET, annotations_path=ANNOTATIONS)
    human_metrics = full["metrics_by_scope"]["HUMAN_VERIFIED_ONLY"]
    human_names = (
        "hybrid_exact_core_v1_accuracy",
        "hybrid_exact_strict_v2_accuracy",
        "hybrid_quantity_accuracy",
        "hybrid_specification_accuracy",
        "hybrid_displayed_price_accuracy",
        "hybrid_effective_price_accuracy",
    )
    bad_cases = {
        row["ambiguity_type"]: {
            "sample_count": row["sample_count"],
            "human_verified_count": row["human_verified_count"],
            "rule_error_count": row["rule_error_count"],
            "hybrid_error_count": row["hybrid_error_count"],
            "human_rule_error_count": row["human_rule_error_count"],
            "human_hybrid_error_count": row["human_hybrid_error_count"],
        }
        for row in full["error_by_ambiguity_type"]
    }
    return {
        "baseline_version": "pricesight_evaluation_baseline_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "metric_contract_version": "v1_core_v2_strict",
        "dataset": {
            "path": "evaluation/datasets/evaluation_v2.jsonl",
            "count": full["dataset_count"],
            "human_verified_count": full["human_verified_count"],
            "split_path": "evaluation/datasets/human_eval_split.json",
            "split_seed": split["seed"],
            "dev_count": split["dev_count"],
            "holdout_count": split["holdout_count"],
            "holdout_frozen": True,
            "provenance_origin": "SOURCE_RECREATED_FROM_EXISTING_ANNOTATION",
        },
        "scopes": scopes,
        "human_verified_only": {
            name: _metric(human_metrics, name)
            for name in human_names
        },
        "bad_cases": bad_cases,
        "human_source_audit": full["human_source_audit"],
    }


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _markdown(report: dict[str, Any], tests: dict[str, Any]) -> str:
    def show(value: dict[str, Any]) -> str:
        accuracy = value["accuracy"]
        rendered = accuracy if isinstance(accuracy, str) else f"{accuracy:.2%}"
        return f"{value['numerator']}/{value['denominator']} ({rendered})"

    lines = [
        "# PriceSight Evaluation Baseline",
        "",
        f"> Frozen at commit `{report['commit']}` on `{report['generated_at']}`. This file is write-once.",
        "> The HUMAN source is reconstructed anonymized offline replay; it is not live-platform accuracy.",
        "",
        "## Tests",
        "",
        f"- Command: `{tests['command']}`",
        f"- Return code: `{tests['returncode']}`",
        f"- Passed: `{tests['passed']}`",
        f"- Branch coverage: `{tests['branch_coverage_percent']}%`",
        "",
        "## Evaluation",
        "",
        "| Scope | CORE | STRICT | Quantity | Specification | Displayed price | Effective price |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        metrics = report["scopes"][scope]["metrics"]
        lines.append(
            f"| {scope} | {show(metrics['hybrid_exact_core_v1_accuracy'])} | "
            f"{show(metrics['hybrid_exact_strict_v2_accuracy'])} | "
            f"{show(metrics['hybrid_quantity_accuracy'])} | "
            f"{show(metrics['hybrid_specification_accuracy'])} | "
            f"{show(metrics['hybrid_displayed_price_accuracy'])} | "
            f"{show(metrics['hybrid_effective_price_accuracy'])} |"
        )
    lines += ["", "## HUMAN_VERIFIED_ONLY", ""]
    human = report["human_verified_only"]
    for name, label in (
        ("hybrid_exact_core_v1_accuracy", "CORE"),
        ("hybrid_exact_strict_v2_accuracy", "STRICT"),
        ("hybrid_quantity_accuracy", "Quantity"),
        ("hybrid_specification_accuracy", "Specification"),
        ("hybrid_displayed_price_accuracy", "Displayed price"),
        ("hybrid_effective_price_accuracy", "Effective price"),
    ):
        lines.append(f"- {label}: {show(human[name])}")
    lines += ["", "## Bad Case counts", "", "| Type | Samples | Human | Hybrid errors | Human hybrid errors |", "| --- | ---: | ---: | ---: | ---: |"]
    for kind, values in sorted(report["bad_cases"].items()):
        lines.append(
            f"| `{kind}` | {values['sample_count']} | {values['human_verified_count']} | "
            f"{values['hybrid_error_count']} | {values['human_hybrid_error_count']} |"
        )
    lines += ["", "## Reproduction", "", "```powershell", "uv run python scripts/build_evaluation_baseline.py", "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze a write-once PriceSight evaluation baseline")
    parser.add_argument("--output-dir", type=Path, default=RESULT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    json_output = output_dir / "baseline.json"
    markdown_output = output_dir / "baseline.md"
    if json_output.exists() or markdown_output.exists():
        raise SystemExit("baseline already exists; refusing to overwrite it")
    tests = _run_tests()
    if tests["returncode"] != 0:
        print(tests["output"], file=sys.stderr)
        raise SystemExit(tests["returncode"])
    report = _build_report()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps({**report, "tests": tests}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_output.write_text(_markdown(report, tests), encoding="utf-8")
    print(json_output)
    print(markdown_output)


if __name__ == "__main__":
    main()
