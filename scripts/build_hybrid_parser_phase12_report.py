"""Build the Phase 12 schema/effective-price/holdout report."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.runner import (  # noqa: E402
    _effective_price_equal,
    _effective_price_eligible,
    _field_equal,
    evaluate_dataset,
    load_dataset,
)


ANNOTATIONS = ROOT / "evaluation/datasets/human_annotations.jsonl"
DATASET = ROOT / "evaluation/datasets/evaluation_v2.jsonl"
SPLIT = ROOT / "evaluation/datasets/human_eval_split.json"
OUTPUT = ROOT / "evaluation/reports/hybrid_parser_phase12_final.md"


def _metric(metrics: dict[str, Any], name: str) -> str:
    value = metrics[name]
    accuracy = value["accuracy"]
    if isinstance(accuracy, str):
        return f"{value['numerator']} / {value['denominator']} = {accuracy}"
    return f"{value['numerator']} / {value['denominator']} = {accuracy:.2%}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _holdout_analysis(report: dict[str, Any], samples: dict[str, Any]) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    clusters: Counter[str] = Counter()
    for case in report["case_results"]:
        sample = samples[case["sample_id"]]
        output = case["final_output"]
        from evaluation.schema import ParsedOutput

        parsed = ParsedOutput.model_validate(output)
        checks: dict[str, bool | None] = {
            "product_match": _field_equal(sample, parsed, "product_name"),
            "quantity_match": _field_equal(sample, parsed, "quantity"),
            "spec_match": _field_equal(sample, parsed, "spec"),
            "displayed_price_match": _field_equal(sample, parsed, "price"),
        }
        if _effective_price_eligible(sample):
            checks["effective_price_match"] = _effective_price_equal(sample, parsed)
        else:
            checks["effective_price_match"] = None
        failures = [name for name, matched in checks.items() if matched is False]
        if not failures:
            primary_failure = "none"
        elif failures[0] == "product_match":
            primary_failure = "product matching"
        elif failures[0] == "quantity_match":
            primary_failure = "quantity parsing"
        elif failures[0] == "spec_match":
            primary_failure = "spec parsing"
        else:
            primary_failure = "price selection"
        if failures:
            clusters[primary_failure] += 1
        rows.append(
            {
                "sample_id": sample.sample_id,
                "ambiguity_type": sample.ambiguity_type.value,
                **checks,
                "primary_failure": primary_failure,
                "secondary_failures": failures[1:],
            }
        )
    return rows, clusters


def _metric_table(lines: list[str], label: str, metrics: dict[str, Any]) -> None:
    lines.extend(
        [
            f"### {label}",
            "",
            "| Parser | Exact | Product | Quantity | Specification | Displayed price | Effective price | Ambiguous case | LLM invocation | Schema failure |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for parser in ("rule", "hybrid"):
        lines.append(
            f"| {parser} | {_metric(metrics, f'{parser}_accuracy')} | "
            f"{_metric(metrics, f'{parser}_product_name_accuracy')} | "
            f"{_metric(metrics, f'{parser}_quantity_accuracy')} | "
            f"{_metric(metrics, f'{parser}_specification_accuracy')} | "
            f"{_metric(metrics, f'{parser}_displayed_price_accuracy')} | "
            f"{_metric(metrics, f'{parser}_effective_price_accuracy')} | "
            f"{_metric(metrics, f'{parser}_ambiguous_case_accuracy')} | "
            f"{_metric(metrics, 'llm_invocation_rate') if parser == 'hybrid' else 'N/A'} | "
            f"{_metric(metrics, 'schema_failure_rate') if parser == 'hybrid' else 'N/A'} |"
        )
    lines.append("")


def main() -> None:
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    full = evaluate_dataset(DATASET, annotations_path=ANNOTATIONS)
    dev = evaluate_dataset(DATASET, set(split["dev_sample_ids"]), ANNOTATIONS)
    holdout = evaluate_dataset(DATASET, set(split["holdout_sample_ids"]), ANNOTATIONS)
    all_samples = {
        sample.sample_id: sample
        for sample in load_dataset(DATASET, ANNOTATIONS)
        if sample.sample_id in set(split["holdout_sample_ids"])
    }
    holdout_rows, clusters = _holdout_analysis(holdout, all_samples)
    human_metrics = full["metrics_by_scope"]["HUMAN_VERIFIED_ONLY"]
    human_samples = [
        sample
        for sample in load_dataset(DATASET, ANNOTATIONS)
        if sample.annotation_status.value == "HUMAN_VERIFIED"
    ]
    schema_failures = [
        case["sample_id"]
        for case in full["case_results"]
        if case["final_output"]["source"] == "rule_fallback"
        and case["sample_id"] in {sample.sample_id for sample in human_samples}
    ]
    effective_eligible = [
        sample.sample_id for sample in human_samples if _effective_price_eligible(sample)
    ]

    lines = [
        "# PriceSight 阶段 12：Schema 补全、Effective Price 与 Holdout 泛化收口",
        "",
        "> 本报告基于仓库内可复现回放。HUMAN_VERIFIED 样本为人工确认的离线脱敏 annotation replay；FakeLLM 是 structured replay，不是线上模型。",
        "",
        "## Schema Fix",
        "",
        "- Unit 新增并纳入 Pydantic/LLM structured schema：`GB`、`TB`、`mm`、`cm`、`m`、`inch`、`sheet`；大小写采用 canonical mapping，非法 `foobar`、`unknown_unit`、`abc123` 仍拒绝。",
        "- 数字存储和长度值进入 `ProductSpecification.components`，不再被当作购买数量；`12GB+256GB` 解析为两个组合 specification component。",
        "- 阶段 11 人工集中的 `GB/mm/inch` schema failure 已消除；剩余 schema failure 属于未纳入本阶段 Unit 家族的 `W/mAh` 或价格语义回放，未通过放宽枚举掩盖。",
        f"- HUMAN_VERIFIED schema failure：{len(schema_failures)} 条，sample_id：{', '.join(f'`{item}`' for item in schema_failures) or '—'}。",
        "",
        "## Effective Price Contract",
        "",
        "- `displayed_price` 表示页面直接展示的挂牌/当前价格；`effective_price` 表示在证据足够时可由文本确定的价格。两者在 `ParsedOutput` 中分开保存，旧 `price` 字段保留为 displayed alias。",
        "- 已支持：显式 `券后89元`/`到手价`、无门槛 `99元，10元券`、数量明确为 2 的第二件半价/免费。第二件半价按两件总价折算为平均单件有效价；数量未知时返回 null。",
        "- `满199减10`、价格区间和组合条件在无法确认满足条件时返回 null；不选择区间端点，不猜测优惠是否生效。",
        f"- HUMAN_VERIFIED effective-price denominator 仅纳入存在价格证据且 expected effective 非空的 {len(effective_eligible)} 条；没有证据的人工字段不进入该字段分母。",
        "",
        "## Holdout Analysis",
        "",
        f"- Frozen split：seed={split['seed']}；DEV={split['dev_count']}；HOLDOUT={split['holdout_count']}。Holdout 在本阶段修改前已冻结。",
        "",
        "| sample_id | ambiguity_type | product | quantity | spec | displayed price | effective price | primary failure | secondary failures |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in holdout_rows:
        lines.append(
            f"| `{row['sample_id']}` | `{row['ambiguity_type']}` | {row['product_match']} | "
            f"{row['quantity_match']} | {row['spec_match']} | {row['displayed_price_match']} | "
            f"{row['effective_price_match'] if row['effective_price_match'] is not None else 'N/A'} | "
            f"{row['primary_failure']} | {', '.join(row['secondary_failures']) or '—'} |"
        )
    lines += [
        "",
        f"- Holdout product-only match：{sum(row['product_match'] and not all(value is True for value in (row['quantity_match'], row['spec_match'], row['displayed_price_match'])) for row in holdout_rows)}。",
        f"- Holdout quantity failures：{sum(row['quantity_match'] is False for row in holdout_rows)}；specification failures：{sum(row['spec_match'] is False for row in holdout_rows)}；displayed-price failures：{sum(row['displayed_price_match'] is False for row in holdout_rows)}；multi-field failures：{sum(len([key for key in ('product_match', 'quantity_match', 'spec_match', 'displayed_price_match') if row[key] is False]) > 1 for row in holdout_rows)}。",
        f"- Failure clusters：`{_json(dict(clusters))}`。Exact 仍可能为 0，即使字段指标非零，因为 exact 要求同一条样本的 product、quantity、spec、displayed price 以及可评估 effective price 同时通过。",
        "",
        "## Before / After",
        "",
        "| Checkpoint | Split | Exact | Product | Quantity | Specification | Displayed price | Effective price |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        "| CLEAN_BASELINE | DEV | 0 / 32 | 13 / 31 | 13 / 32 | 11 / 32 | 0 / 31 | N/A |",
        "| CLEAN_BASELINE | HOLDOUT | 0 / 8 | 3 / 6 | 3 / 8 | 2 / 8 | 0 / 6 | N/A |",
        "| PHASE11_FINAL | DEV | 5 / 32 | 20 / 31 | 23 / 32 | 14 / 32 | 8 / 31 | N/A |",
        "| PHASE11_FINAL | HOLDOUT | 0 / 8 | 3 / 6 | 3 / 8 | 3 / 8 | 2 / 6 | N/A |",
        f"| PHASE12_FINAL | DEV | {_metric(dev['metrics_by_scope']['ALL'], 'hybrid_accuracy')} | {_metric(dev['metrics_by_scope']['ALL'], 'hybrid_product_name_accuracy')} | {_metric(dev['metrics_by_scope']['ALL'], 'hybrid_quantity_accuracy')} | {_metric(dev['metrics_by_scope']['ALL'], 'hybrid_specification_accuracy')} | {_metric(dev['metrics_by_scope']['ALL'], 'hybrid_displayed_price_accuracy')} | {_metric(dev['metrics_by_scope']['ALL'], 'hybrid_effective_price_accuracy')} |",
        f"| PHASE12_FINAL | HOLDOUT | {_metric(holdout['metrics_by_scope']['ALL'], 'hybrid_accuracy')} | {_metric(holdout['metrics_by_scope']['ALL'], 'hybrid_product_name_accuracy')} | {_metric(holdout['metrics_by_scope']['ALL'], 'hybrid_quantity_accuracy')} | {_metric(holdout['metrics_by_scope']['ALL'], 'hybrid_specification_accuracy')} | {_metric(holdout['metrics_by_scope']['ALL'], 'hybrid_displayed_price_accuracy')} | {_metric(holdout['metrics_by_scope']['ALL'], 'hybrid_effective_price_accuracy')} |",
        "",
    ]
    _metric_table(lines, "Regression Metrics / ALL replayable samples", full["metrics_by_scope"]["ALL"])
    _metric_table(lines, "Human Evaluation / HUMAN_VERIFIED_ONLY", human_metrics)
    lines += [
        "## Field Metrics",
        "",
        f"- HUMAN_VERIFIED Hybrid exact：{_metric(human_metrics, 'hybrid_accuracy')}。",
        f"- quantity：{_metric(human_metrics, 'hybrid_quantity_accuracy')}；specification：{_metric(human_metrics, 'hybrid_specification_accuracy')}；displayed price：{_metric(human_metrics, 'hybrid_displayed_price_accuracy')}；effective price：{_metric(human_metrics, 'hybrid_effective_price_accuracy')}。",
        f"- Rule-only exact：{_metric(human_metrics, 'rule_accuracy')}；Hybrid exact：{_metric(human_metrics, 'hybrid_accuracy')}。LLM invocation：{_metric(human_metrics, 'llm_invocation_rate')}；schema failure：{_metric(human_metrics, 'schema_failure_rate')}。",
        "",
        "## Generalization",
        "",
        "- 评级：**LIMITED**。Schema completeness and deterministic price boundaries improved, and DEV field metrics remain reproducible；但 frozen HOLDOUT exact remains 0/8, so the changes do not support a claim of broad complex-product generalization.",
        "- New rules are language-general patterns (`GB/mm/inch`, explicit coupon labels, simple second-item language), not sample_id branches. No expected field is read by the parser; expected annotations are consumed only by the FakeLLM replay harness and evaluator.",
        "- Product-name optimization is intentionally limited. Missing information, popup/loading, dynamic prices, threshold promotions, `W/mAh`, and richer SKU semantics remain explicit failure/insufficient-source cases.",
        "",
        "## Evidence Boundary",
        "",
        f"- Dataset total={full['dataset_count']}；HUMAN_VERIFIED={full['human_verified_count']}；source audit passed={full['human_source_audit']['source_audit_passed']}；synthetic HUMAN_VERIFIED={full['human_source_audit']['synthetic_human_verified_count']}；live platform evidence={full['human_source_audit']['live_platform_evidence_count']}。",
        "- Human metrics are offline human-verified annotation replay, not original live-page captures. FakeLLM is structured replay, not online LLM accuracy. No real platform overall accuracy or production performance claim is valid.",
        "",
        "## Remaining Failure",
        "",
        "- Holdout exact remains 0/8; product/specification matching and price evidence are still the main blockers.",
        "- Effective-price metric is conservative: unsupported threshold/compound promotion semantics remain null or fail, and denominator excludes source text without effective-price evidence.",
        "- Stage 12 closes the planned parser tuning iterations. Future changes are limited to regression/security/build fixes unless a new evaluation phase is explicitly authorized.",
        "",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
