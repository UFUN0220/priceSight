"""Build the contract audit, clean baseline and 40-sample diagnostic table."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.runner import evaluate_dataset, load_dataset  # noqa: E402


ANNOTATIONS = ROOT / "evaluation" / "datasets" / "human_annotations.jsonl"
DATASET = ROOT / "evaluation" / "datasets" / "evaluation_v2.jsonl"
SPLIT = ROOT / "evaluation" / "datasets" / "human_eval_split.json"
OUTPUT = ROOT / "evaluation" / "reports" / "human_parser_clean_baseline.md"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _quantity_equal(expected: Any, actual: Any) -> bool:
    return expected == actual


def _spec_equal(expected: Any, actual: Any) -> bool:
    expected_type = expected.get("package_type") if expected else None
    actual_type = actual.get("package_type") if actual else None
    return expected_type == actual_type


def _price_equal(expected: Any, actual: Any) -> bool:
    if expected is None or actual is None:
        return expected is actual
    return (
        Decimal(str(expected["amount"])) == Decimal(str(actual["amount"]))
        and expected.get("currency") == actual.get("currency")
        and expected.get("price_kind") == actual.get("price_kind")
    )


def _has_price_evidence(sample: Any) -> bool:
    raw_text = ""
    if isinstance(sample.raw_observation, dict):
        raw_text = str(sample.raw_observation.get("text") or sample.raw_observation.get("raw_text") or "")
    return bool(
        re.search(
            r"(?:¥|￥|RMB|人民币|\d+(?:\.\d{1,2})?\s*元|原价|特价|售价|券后|到手价|满\d+减\d+)",
            raw_text,
            flags=re.IGNORECASE,
        )
    )


def _dimensions(sample: Any, output: dict[str, Any]) -> list[str]:
    dimensions: list[str] = []
    expected_name = sample.expected_product_name
    if expected_name is not None and expected_name.casefold() != (output.get("product_name") or "").casefold():
        dimensions.append("product_name")
    expected_quantity = sample.expected_quantity.model_dump(mode="json") if sample.expected_quantity else None
    if sample.expected_quantity is not None and not _quantity_equal(expected_quantity, output.get("quantity")):
        dimensions.append("quantity")
    expected_spec = sample.expected_spec.model_dump(mode="json") if sample.expected_spec else None
    if sample.expected_spec is not None and not _spec_equal(expected_spec, output.get("spec")):
        dimensions.append("specification")
    expected_price = sample.expected_displayed_price or sample.expected_price
    if expected_price is not None and not _price_equal(expected_price.model_dump(mode="json"), output.get("price")):
        dimensions.append("displayed_price" if _has_price_evidence(sample) else "displayed_price_missing_source")
    if sample.expected_effective_price is not None:
        dimensions.append("effective_price_unavailable")
    expected_ambiguous = sample.ambiguity_type.value != "none"
    if output.get("ambiguous") is None or expected_ambiguous != output.get("ambiguous"):
        dimensions.append("ambiguity_detection")
    return dimensions


def _failure_family(dimensions: list[str], output: dict[str, Any]) -> str:
    if "displayed_price" in dimensions:
        return "PRICE_RULE"
    if "quantity" in dimensions:
        return "QUANTITY_RULE"
    if "specification" in dimensions:
        return "SPEC_RULE"
    if "product_name" in dimensions:
        return "PRODUCT_NAME"
    if "ambiguity_detection" in dimensions:
        return "AMBIGUITY_ROUTING"
    if output.get("reason_code") == "llm_schema_or_provider_failure":
        return "LLM_SCHEMA"
    if "effective_price_unavailable" in dimensions:
        return "INSUFFICIENT_INFORMATION"
    return "NONE"


DIMENSION_FAMILY = {
    "displayed_price": "PRICE_RULE",
    "displayed_price_missing_source": "INSUFFICIENT_INFORMATION",
    "quantity": "QUANTITY_RULE",
    "specification": "SPEC_RULE",
    "product_name": "PRODUCT_NAME",
    "ambiguity_detection": "AMBIGUITY_ROUTING",
    "effective_price_unavailable": "INSUFFICIENT_INFORMATION",
}


def build_diagnostics() -> dict[str, Any]:
    samples = {
        sample.sample_id: sample
        for sample in load_dataset(DATASET, ANNOTATIONS)
        if sample.annotation_status.value == "HUMAN_VERIFIED"
    }
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    scopes = {
        "DEV": set(split["dev_sample_ids"]),
        "HOLDOUT": set(split["holdout_sample_ids"]),
        "ALL": set(samples),
    }
    reports = {
        scope: evaluate_dataset(DATASET, sample_ids=ids, annotations_path=ANNOTATIONS)
        for scope, ids in scopes.items()
    }
    all_cases = {case["sample_id"]: case for case in reports["ALL"]["case_results"]}
    diagnostics = []
    for sample_id in sorted(samples):
        sample = samples[sample_id]
        case = all_cases[sample_id]
        rule_dimensions = _dimensions(sample, case["parser_output"])
        hybrid_dimensions = _dimensions(sample, case["final_output"])
        expected_displayed_price = sample.expected_displayed_price or sample.expected_price
        diagnostics.append(
            {
                "sample_id": sample_id,
                "ambiguity_type": sample.ambiguity_type.value,
                "expected_product_name": sample.expected_product_name,
                "actual_product_name": case["final_output"].get("product_name"),
                "expected_quantity": sample.expected_quantity.model_dump(mode="json") if sample.expected_quantity else None,
                "actual_quantity": case["final_output"].get("quantity"),
                "expected_specification": sample.expected_spec.model_dump(mode="json") if sample.expected_spec else None,
                "actual_specification": case["final_output"].get("spec"),
                "expected_displayed_price": expected_displayed_price.model_dump(mode="json") if expected_displayed_price else None,
                "actual_displayed_price": case["final_output"].get("price"),
                "expected_effective_price": sample.expected_effective_price.model_dump(mode="json") if sample.expected_effective_price else None,
                "actual_effective_price": None,
                "rule_output": case["parser_output"],
                "hybrid_output": case["final_output"],
                "failure_dimensions": {
                    "rule": rule_dimensions,
                    "hybrid": hybrid_dimensions,
                },
                "failure_family": {
                    "rule": _failure_family(rule_dimensions, case["parser_output"]),
                    "hybrid": _failure_family(hybrid_dimensions, case["final_output"]),
                },
            }
        )
    return {"split": split, "scope_reports": reports, "diagnostics": diagnostics}


def _metric(report: dict[str, Any], parser: str, field: str) -> dict[str, Any]:
    metrics = report["metrics_by_scope"]["HUMAN_VERIFIED_ELIGIBLE"]
    return metrics[f"{parser}_{field}_accuracy"]


def _metric_text(metric: dict[str, Any]) -> str:
    accuracy = metric["accuracy"]
    return "N/A" if accuracy == "NOT_AVAILABLE" else f"{metric['numerator']} / {metric['denominator']} = {accuracy:.2%}"


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Human Parser Clean Baseline",
        "",
        "> `CLEAN_BASELINE`：Evaluation Contract 审计后、Parser 未修改前的 40 条 eligible human 离线样本基线。source 均为 SOURCE_RECREATED_FROM_EXISTING_ANNOTATION，不是实时网页 capture。",
        "",
        "## Evaluation Contract Audit",
        "",
        "- `ambiguous_case_accuracy` 表示 ambiguity_type 非 none 的样本上的完整字段准确率；它不等于 ambiguity detection。",
        "- 新增 `ambiguous_detection_accuracy` 诊断 output.ambiguous 与 ambiguity_type 是否一致；Hybrid 成功消解歧义后 output.ambiguous=false，因此不能把该字段当成案例准确率。",
        "- `displayed_price 0 / 37` 不是金额 Decimal/字符串 comparator 问题；当前 PriceParser 只识别 ¥/￥/RMB，而新增 raw_text 大多使用“元”或未含价格，属于 PRICE_RULE/input coverage 失败。",
        "- `effective_price` 分母为 0 是正确的 N/A：当前 ParsedOutput 没有 effective price 字段，且不参与 overall。",
        "- overall 不要求 effective_price，也不会要求 expected=null 的字段被猜出；0 / 40 主要来自 product/quantity/spec/price 实际不匹配。",
        "- quantity 比较会把 L→ml、kg→g 归一到同一基准单位，但 count/container_unit 仍严格比较；spec 当前只比较 package_type，notes 不参与比较，未以宽松相似度掩盖错误。",
        "",
        "## Clean Baseline",
        "",
        "| Split | Parser | overall | product_name | quantity | specification | displayed_price | effective_price | ambiguous_case | ambiguous_detection |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        report = data["scope_reports"][scope]
        for parser in ("rule", "hybrid"):
            scope_metrics = report["metrics_by_scope"]["HUMAN_VERIFIED_ELIGIBLE"]
            lines.append(
                f"| {scope} | {parser} | {_metric_text(scope_metrics[f'{parser}_accuracy'])} | "
                f"{_metric_text(_metric(report, parser, 'product_name'))} | {_metric_text(_metric(report, parser, 'quantity'))} | "
                f"{_metric_text(_metric(report, parser, 'specification'))} | {_metric_text(_metric(report, parser, 'displayed_price'))} | "
                f"{_metric_text(_metric(report, parser, 'effective_price'))} | "
                f"{_metric_text(_metric(report, parser, 'ambiguous_case'))} | "
                f"{_metric_text(_metric(report, parser, 'ambiguous_detection'))} |"
            )
    lines += [
        "",
        "## Split",
        "",
        f"- seed：{data['split']['seed']}；DEV：{data['split']['dev_count']}；HOLDOUT：{data['split']['holdout_count']}。",
        "- HOLDOUT manifest 已冻结，Parser 调优期间不得按 HOLDOUT 结果改单独规则。",
        "",
        "## Failure Taxonomy",
        "",
        "| Failure family | count | affected sample_ids |",
        "| --- | ---: | --- |",
    ]
    family_ids: dict[str, set[str]] = {}
    for diagnostic in data["diagnostics"]:
        for dimension in diagnostic["failure_dimensions"]["hybrid"]:
            family = DIMENSION_FAMILY.get(dimension, "UNCLASSIFIED")
            family_ids.setdefault(family, set()).add(diagnostic["sample_id"])
    for family, ids in sorted(family_ids.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.append(f"| `{family}` | {len(ids)} | {', '.join(f'`{item}`' for item in sorted(ids))} |")
    lines += [
        "",
        "## Diagnostic Table",
        "",
        "| sample_id | ambiguity | expected/actual product | expected/actual quantity | expected/actual spec | expected/actual displayed price | expected/actual effective price | failure_dimensions |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for diagnostic in data["diagnostics"]:
        lines.append(
            f"| `{diagnostic['sample_id']}` | `{diagnostic['ambiguity_type']}` | "
            f"`{_json(diagnostic['expected_product_name'])}` / `{_json(diagnostic['actual_product_name'])}` | "
            f"`{_json(diagnostic['expected_quantity'])}` / `{_json(diagnostic['actual_quantity'])}` | "
            f"`{_json(diagnostic['expected_specification'])}` / `{_json(diagnostic['actual_specification'])}` | "
            f"`{_json(diagnostic['expected_displayed_price'])}` / `{_json(diagnostic['actual_displayed_price'])}` | "
            f"`{_json(diagnostic['expected_effective_price'])}` / `{_json(diagnostic['actual_effective_price'])}` | "
            f"`{_json(diagnostic['failure_dimensions'])}` |"
        )
    lines += [
        "",
        "## Parser Boundary",
        "",
        "Parser unchanged during Contract Audit and Clean Baseline generation.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    data = build_diagnostics()
    OUTPUT.write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"report": OUTPUT.as_posix(), "samples": len(data["diagnostics"]), "status": "CLEAN_BASELINE"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
