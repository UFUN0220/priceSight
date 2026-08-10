"""Run the frozen dataset once under the Phase 13 metric contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.runner import evaluate_dataset  # noqa: E402


def main() -> None:
    dataset = ROOT / "evaluation/datasets/evaluation_v2.jsonl"
    annotations = ROOT / "evaluation/datasets/human_annotations.jsonl"
    split = json.loads((ROOT / "evaluation/datasets/human_eval_split.json").read_text(encoding="utf-8"))
    scopes: dict[str, dict[str, Any]] = {}
    for name, sample_ids in (
        ("DEV", set(split["dev_sample_ids"])),
        ("HOLDOUT", set(split["holdout_sample_ids"])),
        ("ALL", None),
    ):
        report = evaluate_dataset(dataset, sample_ids, annotations)
        scopes[name] = {
            "metrics": report["metrics_by_scope"]["ALL"],
            "dataset_count": report["dataset_count"],
            "case_results": report["case_results"],
        }
    full = evaluate_dataset(dataset, annotations_path=annotations)
    output = {
        "report_version": "phase13_final_evaluation_v1",
        "metric_contract_version": "v1_core_v2_strict",
        "dataset_manifest": "evaluation/reports/final_dataset_manifest.json",
        "split_seed": split["seed"],
        "scopes": scopes,
        "human_verified_only": {
            "metrics": full["metrics_by_scope"]["HUMAN_VERIFIED_ONLY"],
            "dataset_count": full["human_verified_count"],
        },
        "evidence_boundary": {
            "human_verified_eligible": full["human_verified_count"],
            "provenance_passed": full["human_source_audit"]["source_audit_passed"],
            "source_origin": "SOURCE_RECREATED_FROM_EXISTING_ANNOTATION",
            "live_platform_evidence": full["human_source_audit"]["live_platform_evidence_count"],
            "llm": "FakeLLM structured replay; not online model accuracy",
        },
    }
    json_path = ROOT / "evaluation/reports/evaluation_final_freeze.json"
    md_path = ROOT / "evaluation/reports/evaluation_final_freeze.md"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def metric(scope: str, name: str) -> str:
        value = output["scopes"][scope]["metrics"][name]
        accuracy = value["accuracy"]
        shown = accuracy if isinstance(accuracy, str) else f"{accuracy:.2%}"
        return f"{value['numerator']} / {value['denominator']} = {shown}"

    lines = [
        "# PriceSight Phase 13 Final Evaluation",
        "",
        "> Frozen dataset and `evaluation/METRIC_CONTRACT.md`; no parser tuning was performed for this report.",
        "",
        "## Exact",
        "",
        "| Scope | EXACT_CORE_V1 | EXACT_STRICT_V2 |",
        "| --- | --- | --- |",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        lines.append(
            f"| {scope} | {metric(scope, 'hybrid_exact_core_v1_accuracy')} | {metric(scope, 'hybrid_exact_strict_v2_accuracy')} |"
        )
    lines += [
        "",
        "## Fields",
        "",
        "| Scope | Product | Quantity | Specification | Displayed price | Effective price |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        lines.append(
            f"| {scope} | {metric(scope, 'hybrid_product_name_accuracy')} | "
            f"{metric(scope, 'hybrid_quantity_accuracy')} | {metric(scope, 'hybrid_specification_accuracy')} | "
            f"{metric(scope, 'hybrid_displayed_price_accuracy')} | {metric(scope, 'hybrid_effective_price_accuracy')} |"
        )
    human = output["human_verified_only"]["metrics"]
    lines += [
        "",
        "## Human Verified Only",
        "",
        f"- CORE：{human['hybrid_exact_core_v1_accuracy']['numerator']} / {human['hybrid_exact_core_v1_accuracy']['denominator']}",
        f"- STRICT：{human['hybrid_exact_strict_v2_accuracy']['numerator']} / {human['hybrid_exact_strict_v2_accuracy']['denominator']}",
        f"- Quantity：{human['hybrid_quantity_accuracy']['numerator']} / {human['hybrid_quantity_accuracy']['denominator']}",
        f"- Specification：{human['hybrid_specification_accuracy']['numerator']} / {human['hybrid_specification_accuracy']['denominator']}",
        f"- Displayed price：{human['hybrid_displayed_price_accuracy']['numerator']} / {human['hybrid_displayed_price_accuracy']['denominator']}",
        f"- Effective price：{human['hybrid_effective_price_accuracy']['numerator']} / {human['hybrid_effective_price_accuracy']['denominator']}",
        f"- FakeLLM invocation：{human['llm_invocation_rate']['numerator']} / {human['llm_invocation_rate']['denominator']}",
        f"- Schema failure：{human['schema_failure_rate']['numerator']} / {human['schema_failure_rate']['denominator']}",
        "",
        "## Boundary",
        "",
        "HUMAN samples are reconstructed anonymized offline replay. FakeLLM is structured replay. These metrics do not establish live platform accuracy, online LLM accuracy, production throughput, or production latency.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
