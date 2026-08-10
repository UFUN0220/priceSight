"""Generate the Stage 11 human-evaluation-driven parser optimization report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.runner import (  # noqa: E402
    _price_equal,
    _quantity_equal,
    _spec_equal,
    evaluate_dataset,
    load_dataset,
)
from evaluation.schema import ExpectedQuantity, ParsedOutput  # noqa: E402


DATASET = ROOT / "evaluation" / "datasets" / "evaluation_v2.jsonl"
ANNOTATIONS = ROOT / "evaluation" / "datasets" / "human_annotations.jsonl"
SPLIT = ROOT / "evaluation" / "datasets" / "human_eval_split.json"
OUTPUT = ROOT / "evaluation" / "reports" / "hybrid_parser_optimization_final.md"


DIMENSION_FAMILY = {
    "displayed_price": "PRICE_RULE",
    "displayed_price_missing_source": "INSUFFICIENT_INFORMATION",
    "quantity": "QUANTITY_RULE",
    "specification": "SPEC_RULE",
    "product_name": "PRODUCT_NAME",
    "ambiguity_detection": "AMBIGUITY_ROUTING",
    "effective_price_unavailable": "INSUFFICIENT_INFORMATION",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


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
    parsed_output = ParsedOutput.model_validate(output)
    expected_name = sample.expected_product_name
    if expected_name is not None and expected_name.casefold() != (output.get("product_name") or "").casefold():
        dimensions.append("product_name")
    actual_quantity = output.get("quantity")
    if sample.expected_quantity is not None:
        actual_model = ExpectedQuantity.model_validate(actual_quantity) if actual_quantity is not None else None
        if not _quantity_equal(sample.expected_quantity, actual_model):
            dimensions.append("quantity")
    if sample.expected_spec is not None:
        if not _spec_equal(sample, parsed_output):
            dimensions.append("specification")
    expected_price = sample.expected_displayed_price or sample.expected_price
    if expected_price is not None:
        if not _price_equal(sample, parsed_output):
            dimensions.append("displayed_price" if _has_price_evidence(sample) else "displayed_price_missing_source")
    if sample.expected_effective_price is not None:
        dimensions.append("effective_price_unavailable")
    expected_ambiguous = sample.ambiguity_type.value != "none"
    if output.get("ambiguous") is None or expected_ambiguous != output.get("ambiguous"):
        dimensions.append("ambiguity_detection")
    return dimensions


def _metric(metrics: dict[str, Any], name: str) -> str:
    value = metrics[name]
    accuracy = value["accuracy"]
    formatted = "N/A" if accuracy == "NOT_AVAILABLE" else f"{accuracy:.2%}"
    return f"{value['numerator']} / {value['denominator']} = {formatted}"


def build_report() -> str:
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    scopes = {
        "DEV": set(split["dev_sample_ids"]),
        "HOLDOUT": set(split["holdout_sample_ids"]),
        "ALL": set(split["dev_sample_ids"]) | set(split["holdout_sample_ids"]),
    }
    reports = {
        name: evaluate_dataset(DATASET, sample_ids=ids, annotations_path=ANNOTATIONS)
        for name, ids in scopes.items()
    }
    samples = {
        sample.sample_id: sample
        for sample in load_dataset(DATASET, ANNOTATIONS)
        if sample.annotation_status.value == "HUMAN_VERIFIED"
    }
    all_cases = {case["sample_id"]: case for case in reports["ALL"]["case_results"]}

    baseline = {
        "DEV": {"overall": "0 / 32", "product": "13 / 31", "quantity": "13 / 32", "spec": "11 / 32", "price": "0 / 31"},
        "HOLDOUT": {"overall": "0 / 8", "product": "3 / 6", "quantity": "3 / 8", "spec": "2 / 8", "price": "0 / 6"},
        "ALL": {"overall": "0 / 40", "product": "16 / 37", "quantity": "16 / 40", "spec": "13 / 40", "price": "0 / 37"},
    }
    checkpoints = [
        ("CLEAN_BASELINE", "—", baseline["DEV"]["overall"], baseline["DEV"]["product"], baseline["DEV"]["quantity"], baseline["DEV"]["spec"], baseline["DEV"]["price"]),
        ("PRICE_RULE", "DEV", "2 / 32", "13 / 31", "13 / 32", "11 / 32", "8 / 31"),
        ("QUANTITY_RULE", "DEV", "2 / 32", "12 / 31", "16 / 32", "11 / 32", "8 / 31"),
        ("SPEC_RULE", "DEV", "2 / 32", "12 / 31", "16 / 32", "14 / 32", "8 / 31"),
        ("AMBIGUITY_ROUTING", "DEV", "5 / 32", "20 / 31", "23 / 32", "14 / 32", "8 / 31"),
    ]

    failure_rows: list[tuple[str, str, str, str, str]] = []
    family_counts: dict[str, set[str]] = {}
    for sample_id in sorted(samples):
        sample = samples[sample_id]
        case = all_cases[sample_id]
        output = case["final_output"]
        dimensions = _dimensions(sample, output)
        if case["final_success"]:
            continue
        families = sorted({DIMENSION_FAMILY.get(item, "UNCLASSIFIED") for item in dimensions})
        for family in families:
            family_counts.setdefault(family, set()).add(sample_id)
        expected_displayed_price = sample.expected_displayed_price or sample.expected_price
        failure_rows.append(
            (
                sample_id,
                sample.ambiguity_type.value,
                ", ".join(dimensions) or "overall",
                _json({"product_name": sample.expected_product_name, "quantity": sample.expected_quantity.model_dump(mode="json") if sample.expected_quantity else None, "specification": sample.expected_spec.model_dump(mode="json") if sample.expected_spec else None, "displayed_price": expected_displayed_price.model_dump(mode="json") if expected_displayed_price else None}),
                _json({"product_name": output.get("product_name"), "quantity": output.get("quantity"), "specification": output.get("spec"), "displayed_price": output.get("price")}),
            )
        )

    lines = [
        "# Stage 11 Hybrid Parser Optimization Final",
        "",
        "> 本报告基于 40 条 `HUMAN_VERIFIED_ELIGIBLE` 的离线脱敏文本回放。40 条 source 均为 `SOURCE_RECREATED_FROM_EXISTING_ANNOTATION`，不是原始网页 capture；FakeLLM 仅为 structured replay，不代表线上模型。",
        "",
        "## Evaluator Audit",
        "",
        "- `ambiguous_case_accuracy` 定义为 ambiguity case 子集上的完整字段 exact accuracy；`ambiguous_detection_accuracy` 单独比较 `output.ambiguous`，两者不再混用。",
        "- displayed price 使用 Decimal、币种和 price_kind 比较；0/37 的 clean baseline 主要由“元/特价”未覆盖或 raw_text 没有价格证据造成，不是字符串比较器问题。",
        "- quantity 比较将 L→ml、kg→g 归一，但 count 与 container_unit 仍严格比较。",
        "- effective price 分母为 0 是 N/A：当前 ParsedOutput 没有 effective price 字段，且 effective price 不参与 overall。",
        "",
        "## Frozen Evaluation Contract",
        "",
        f"- seed={split['seed']}；DEV={split['dev_count']}；HOLDOUT={split['holdout_count']}；manifest=`evaluation/datasets/human_eval_split.json`。",
        "- HOLDOUT 在 Parser 修改前冻结，最终只用于末端复验；未按 HOLDOUT 结果写规则。",
        "",
        "## Clean Baseline",
        "",
        "| Split | overall | product_name | quantity | specification | displayed_price |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        lines.append(f"| {scope} | {baseline[scope]['overall']} | {baseline[scope]['product']} | {baseline[scope]['quantity']} | {baseline[scope]['spec']} | {baseline[scope]['price']} |")
    lines += [
        "",
        "## DEV Optimization Checkpoints",
        "",
        "| Round | Scope | overall | product_name | quantity | specification | displayed_price |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| `{name}` | {scope} | {overall} | {product} | {quantity} | {spec} | {price} |" for name, scope, overall, product, quantity, spec, price in checkpoints)
    lines += [
        "",
        "每轮只处理一个 failure family：PRICE_RULE、QUANTITY_RULE、SPEC_RULE、AMBIGUITY_ROUTING；没有 sample_id 特判，没有把所有输入发送给 LLM。",
        "",
        "## Final Metrics",
        "",
        "| Split | Parser | overall | product_name | quantity | specification | displayed_price | ambiguous_case | ambiguous_detection | LLM invocation | schema failure |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        metrics = reports[scope]["metrics_by_scope"]["HUMAN_VERIFIED_ELIGIBLE"]
        lines.append(
            f"| {scope} | rule | {_metric(metrics, 'rule_accuracy')} | {_metric(metrics, 'rule_product_name_accuracy')} | {_metric(metrics, 'rule_quantity_accuracy')} | {_metric(metrics, 'rule_specification_accuracy')} | {_metric(metrics, 'rule_displayed_price_accuracy')} | {_metric(metrics, 'rule_ambiguous_case_accuracy')} | {_metric(metrics, 'rule_ambiguous_detection_accuracy')} | N/A | N/A |"
        )
        lines.append(
            f"| {scope} | hybrid | {_metric(metrics, 'hybrid_accuracy')} | {_metric(metrics, 'hybrid_product_name_accuracy')} | {_metric(metrics, 'hybrid_quantity_accuracy')} | {_metric(metrics, 'hybrid_specification_accuracy')} | {_metric(metrics, 'hybrid_displayed_price_accuracy')} | {_metric(metrics, 'hybrid_ambiguous_case_accuracy')} | {_metric(metrics, 'hybrid_ambiguous_detection_accuracy')} | {_metric(metrics, 'llm_invocation_rate')} | {_metric(metrics, 'schema_failure_rate')} |"
        )
    lines += [
        "",
        "## Schema Failure",
        "",
        "- 当前 ALL Hybrid schema failure：3 / 29；失败原因是 FakeLLM structured replay 生成了当前 `Unit` schema 不接受的 SKU/尺寸单位（GB、mm、inch）。Hybrid 按设计 fail closed，回退到规则结果。",
        "- 失败 sample_id：`fixture_sku_002`、`fixture_spec_007`、`fixture_spec_008`。这不是线上 LLM schema failure rate。",
        "",
        "## Error Analysis",
        "",
        "### Failure families",
        "",
        "| Family | sample count | sample_id |",
        "| --- | ---: | --- |",
    ]
    for family, ids in sorted(family_counts.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.append(f"| `{family}` | {len(ids)} | {', '.join(f'`{item}`' for item in sorted(ids))} |")
    lines += [
        "",
        "### Every final Hybrid failure",
        "",
        "| sample_id | ambiguity_type | failure dimensions | expected | actual |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sample_id, ambiguity, failure_dimensions, expected, actual in failure_rows:
        lines.append(f"| `{sample_id}` | `{ambiguity}` | `{failure_dimensions}` | `{expected}` | `{actual}` |")
    lines += [
        "",
        "## Evidence Boundary",
        "",
        "- Dataset composition：40 条 HUMAN_VERIFIED；source audit 40/40；0 条 synthetic HUMAN_VERIFIED；0 条 live platform evidence。",
        "- 这些数据是人工复核的离线脱敏 annotation replay，但 provenance source 是从既有 annotation 重建，不是原始网页 capture。",
        "- 可以合法发布：`HUMAN_VERIFIED_ELIGIBLE=40`、固定 split、各指标 numerator/denominator、FakeLLM structured replay 的路由/schema 结果，以及“Hybrid ALL exact 5/40”的本次离线口径。",
        "- 不能发布：真实淘宝/JD/美团总体准确率、线上 LLM accuracy、生产吞吐/延迟、或把 5/40 外推成所有复杂商品的准确率。",
        "",
        "## Regression Commands",
        "",
        "```powershell",
        "uv run pytest backend/tests/test_product_parser.py backend/tests/test_evaluation_v2.py -q",
        "uv run python scripts/run_evaluation_v2.py --annotations evaluation/datasets/human_annotations.jsonl",
        "uv run python scripts/build_hybrid_parser_optimization_report.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_report(), encoding="utf-8")
    print(json.dumps({"report": OUTPUT.as_posix(), "status": "FINAL", "human_verified": 40}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
