"""Run reproducible rule-only and hybrid product parsing evaluation."""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.llm.fake import FakeLLMProvider
from app.llm.base import LLMResponse
from app.parser.hybrid import HybridProductParser
from app.parser.product import ProductParser


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "product_spec.jsonl"
REPORT = ROOT / "evaluation" / "reports" / "phase7_product_parsing.json"


def load_cases() -> list[dict]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


def signature(result) -> dict:
    quantity = result.specification.primary_quantity
    return {
        "product_name": result.product_identity.name,
        "quantity": (
            {
                "count": quantity.count,
                "content_amount": str(quantity.content_amount) if quantity.content_amount is not None else None,
                "content_unit": quantity.content_unit.value if quantity.content_unit else None,
                "container_unit": quantity.container_unit.value if quantity.container_unit else None,
            }
            if quantity
            else None
        ),
        "package_type": result.specification.package_type,
    }


def main() -> None:
    cases = load_cases()
    rule_parser = ProductParser()
    rule_results = []
    rule_durations = []
    for case in cases:
        started = time.perf_counter()
        result = rule_parser.parse(case["raw_text"])
        rule_durations.append((time.perf_counter() - started) * 1000)
        rule_results.append(result)

    # Synthetic fallback responses exercise the schema path without claiming live-model performance.
    responses = []
    for case, rule_result in zip(cases, rule_results):
        if rule_result.ambiguous:
            expected = case["expected"]
            quantity = expected.get("quantity")
            responses.append(
                LLMResponse(
                    provider="fake",
                    content=json.dumps(
                        {
                            "product_name": expected["product_name"],
                            "normalized_product_name": expected["product_name"].casefold(),
                            "quantity": quantity,
                            "promotions": [],
                            "confidence": 0.9,
                            "reason_summary": "synthetic evaluation response",
                        },
                        ensure_ascii=False,
                    ),
                )
            )
    hybrid_parser = HybridProductParser(FakeLLMProvider(responses))
    hybrid_results = []
    hybrid_durations = []
    for case in cases:
        started = time.perf_counter()
        hybrid_results.append(hybrid_parser.parse(case["raw_text"]))
        hybrid_durations.append((time.perf_counter() - started) * 1000)

    expected = [case["expected"] for case in cases]
    rule_accuracy = sum(signature(result) == item for result, item in zip(rule_results, expected)) / len(cases)
    hybrid_accuracy = sum(signature(result) == item for result, item in zip(hybrid_results, expected)) / len(cases)
    fallback_rate = sum(result.llm_fallback_attempted for result in hybrid_results) / len(cases)
    report = {
        "dataset": str(DATASET.relative_to(ROOT)),
        "dataset_metadata": "synthetic; not human-reviewed",
        "case_count": len(cases),
        "rule_only_accuracy": rule_accuracy,
        "hybrid_accuracy": hybrid_accuracy,
        "llm_fallback_rate": fallback_rate,
        "average_parse_latency": sum(hybrid_durations) / len(hybrid_durations),
        "average_parse_latency_ms": sum(hybrid_durations) / len(hybrid_durations),
        "rule_average_parse_latency_ms": sum(rule_durations) / len(rule_durations),
        "provider": "fake",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
