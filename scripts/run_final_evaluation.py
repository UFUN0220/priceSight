"""Aggregate measured phase reports into the final evaluation artifact."""

from __future__ import annotations

import json
from pathlib import Path
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "evaluation" / "reports"
OUTPUT = REPORT_DIR / "phase13_final_evaluation.json"


def read_report(name: str) -> dict[str, Any]:
    return json.loads((REPORT_DIR / name).read_text(encoding="utf-8"))


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def main() -> None:
    compression = read_report("phase3_tree_compression.json")
    parsing = read_report("phase7_product_parsing.json")
    benchmark = read_report("phase12_benchmark.json")

    compression_cases = [
        item["stats"]
        for item in compression["cases"]
        if item["stats"]["raw_node_count"] > 0
    ]
    compression_ratios = [float(item["compression_ratio"]) for item in compression_cases]
    tasks = benchmark["tasks"]["raw_results"]
    action_rates = [float(item["action_success_rate"]) for item in tasks]
    safety_results = [bool(item["safety_stop_correct"]) for item in tasks]

    result = {
        "phase": 13,
        "scope": "final measured offline evaluation and implementation audit",
        "measurement_scopes": {
            "tree_compression": "synthetic fixtures",
            "product_parsing": parsing["dataset_metadata"],
            "task_and_action": "controlled Mock Shopping App / Python mock device",
            "cache_and_transport": "synthetic fixture sources / fake transport",
            "real_app": "not measured",
        },
        "metrics": {
            "tree_compression_ratio_retained_mean": mean(compression_ratios),
            "tree_compression_case_count": len(compression_cases),
            "product_parsing_rule_only_accuracy": parsing["rule_only_accuracy"],
            "product_parsing_hybrid_accuracy": parsing["hybrid_accuracy"],
            "task_success_rate": benchmark["tasks"]["task_success_rate"],
            "action_success_rate": mean(action_rates),
            "average_retries": mean([float(item["retries"]) for item in tasks]),
            "average_steps": benchmark["tasks"]["average_steps_per_task"],
            "average_llm_calls": benchmark["tasks"]["average_llm_calls_per_task"],
            "end_to_end_latency_ms_mean": mean([float(item["latency_ms"]) for item in tasks]),
            "cache_hit_rate_warm_run": benchmark["cache"]["second_run"]["hit_rate"],
            "safety_stop_accuracy": sum(safety_results) / len(safety_results) if safety_results else 0.0,
        },
        "benchmark_reference": {
            "polling_latency_ms_mean": benchmark["polling_latency_ms"]["mean_ms"],
            "event_driven_latency_ms_mean": benchmark["event_driven_latency_ms"]["mean_ms"],
            "iterations": benchmark["conditions"]["iterations"],
        },
        "limitations": [
            "All reported evaluation datasets and task runs are synthetic or controlled mock runs.",
            "No dataset is human-reviewed unless explicitly labeled otherwise; the current parsing dataset is not human-reviewed.",
            "Real Android devices, real shopping applications, and live provider calls were not used.",
            "No production throughput, network latency, or real-platform success rate is claimed.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
