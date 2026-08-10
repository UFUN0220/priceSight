"""Run the frozen evaluation after the targeted parser/pricing changes."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "evaluation" / "results"
BASELINE = RESULT_DIR / "baseline.json"
DATASET = ROOT / "evaluation" / "datasets" / "evaluation_v2.jsonl"
ANNOTATIONS = ROOT / "evaluation" / "datasets" / "human_annotations.jsonl"
SPLIT = ROOT / "evaluation" / "datasets" / "human_eval_split.json"


def _metric(metrics: dict[str, Any], name: str) -> dict[str, Any]:
    value = metrics[name]
    return {key: value[key] for key in ("numerator", "denominator", "accuracy")}


def _scope(report: dict[str, Any]) -> dict[str, Any]:
    names = (
        "hybrid_exact_core_v1_accuracy",
        "hybrid_exact_strict_v2_accuracy",
        "hybrid_quantity_accuracy",
        "hybrid_specification_accuracy",
        "hybrid_displayed_price_accuracy",
        "hybrid_effective_price_accuracy",
        "hybrid_ambiguous_detection_accuracy",
    )
    return {
        "dataset_count": report["dataset_count"],
        "metrics": {name: _metric(report["metrics_by_scope"]["ALL"], name) for name in names},
        "bad_cases": {
            row["ambiguity_type"]: {
                "sample_count": row["sample_count"],
                "hybrid_error_count": row["hybrid_error_count"],
            }
            for row in report["error_by_ambiguity_type"]
        },
        "abstention_counts": {
            "ambiguous": sum(bool(item["final_output"].get("ambiguous")) for item in report["case_results"]),
            "missing_displayed_price": sum(item["final_output"].get("displayed_price") is None for item in report["case_results"]),
            "missing_effective_price": sum(item["final_output"].get("effective_price") is None for item in report["case_results"]),
        },
    }


def _run() -> dict[str, Any]:
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
        scopes[name] = _scope(evaluate_dataset(DATASET, ids, ANNOTATIONS))
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
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    deltas = {}
    for name in scopes["ALL"]["bad_cases"]:
        before = baseline["bad_cases"].get(name, {}).get("hybrid_error_count", 0)
        after = scopes["ALL"]["bad_cases"][name]["hybrid_error_count"]
        deltas[name] = {"baseline": before, "final": after, "delta": after - before}
    return {
        "final_version": "pricesight_targeted_improvement_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_path": "evaluation/results/baseline.json",
        "baseline_commit": baseline["commit"],
        "metric_contract_version": "v1_core_v2_strict",
        "split_seed": split["seed"],
        "scopes": scopes,
        "human_verified_only": {
            name: _metric(human_metrics, name)
            for name in human_names
        },
        "bad_case_delta": deltas,
        "human_source_audit": full["human_source_audit"],
        "evidence_boundary": {
            "source_origin": "SOURCE_RECREATED_FROM_EXISTING_ANNOTATION",
            "live_platform_evidence": full["human_source_audit"]["live_platform_evidence_count"],
            "llm": "FakeLLM structured replay; not online model accuracy",
        },
    }


def _show(metric: dict[str, Any]) -> str:
    accuracy = metric["accuracy"]
    rendered = accuracy if isinstance(accuracy, str) else f"{accuracy:.2%}"
    return f"{metric['numerator']}/{metric['denominator']} ({rendered})"


def _markdown(report: dict[str, Any], baseline: dict[str, Any]) -> str:
    lines = [
        "# PriceSight Targeted Improvement Evaluation",
        "",
        f"> Final replay generated at `{report['generated_at']}`; baseline remains frozen at `{report['baseline_commit']}`.",
        "> No annotation, DEV/HOLDOUT membership or metric definition was changed.",
        "",
        "## Baseline → final",
        "",
        "| Scope | CORE | STRICT | Quantity | Specification | Displayed price | Effective price |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        before = baseline["scopes"][scope]["metrics"]
        after = report["scopes"][scope]["metrics"]
        def pair(name: str) -> str:
            return f"{_show(before[name])} → {_show(after[name])}"
        lines.append(
            f"| {scope} | {pair('hybrid_exact_core_v1_accuracy')} | {pair('hybrid_exact_strict_v2_accuracy')} | "
            f"{pair('hybrid_quantity_accuracy')} | {pair('hybrid_specification_accuracy')} | "
            f"{pair('hybrid_displayed_price_accuracy')} | {pair('hybrid_effective_price_accuracy')} |"
        )
    lines += ["", "## HUMAN_VERIFIED_ONLY", ""]
    for name, label in (
        ("hybrid_exact_core_v1_accuracy", "CORE"),
        ("hybrid_exact_strict_v2_accuracy", "STRICT"),
        ("hybrid_quantity_accuracy", "Quantity"),
        ("hybrid_specification_accuracy", "Specification"),
        ("hybrid_displayed_price_accuracy", "Displayed price"),
        ("hybrid_effective_price_accuracy", "Effective price"),
    ):
        lines.append(f"- {label}: {_show(report['human_verified_only'][name])}")
    lines += ["", "## Bad Case delta", "", "| Type | Baseline errors | Final errors | Delta |", "| --- | ---: | ---: | ---: |"]
    for kind, values in sorted(report["bad_case_delta"].items()):
        lines.append(f"| `{kind}` | {values['baseline']} | {values['final']} | {values['delta']:+d} |")
    lines += [
        "",
        "## Abstention evidence",
        "",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        counts = report["scopes"][scope]["abstention_counts"]
        lines.append(
            f"- {scope}: ambiguous={counts['ambiguous']}, missing displayed={counts['missing_displayed_price']}, "
            f"missing effective={counts['missing_effective_price']}"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "HUMAN rows are reconstructed anonymized offline replay. HOLDOUT remains frozen and is reported even when it is low. FakeLLM, Mock Android, Browser Mock and fixture adapters are controlled evidence, not real-platform accuracy.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Replay the frozen evaluation after targeted changes")
    parser.add_argument("--output-dir", type=Path, default=RESULT_DIR)
    args = parser.parse_args()
    report = _run()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_output = output_dir / "final.json"
    markdown_output = output_dir / "final.md"
    json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_output.write_text(_markdown(report, baseline), encoding="utf-8")
    print(json_output)
    print(markdown_output)


if __name__ == "__main__":
    main()
