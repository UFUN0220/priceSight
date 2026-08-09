"""Generate the Phase 3 before/after Hybrid Parser report."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.runner import evaluate_dataset  # noqa: E402


BEFORE = ROOT / "evaluation/reports/hybrid_parser_before_optimization.json"
AFTER_JSON = ROOT / "evaluation/reports/hybrid_parser_after_optimization.json"
AFTER_MD = ROOT / "evaluation/reports/hybrid_parser_after_optimization.md"
DATASET = ROOT / "evaluation/datasets/evaluation_v2.jsonl"


def _metric(report: dict, key: str) -> str:
    value = report[key]
    if value["denominator"] == 0:
        return "N/A (0/0)"
    return f"{value['numerator']}/{value['denominator']} ({value['accuracy']:.4f})"


def main() -> None:
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    after = evaluate_dataset(DATASET)
    AFTER_JSON.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sample_metadata = {
        sample["sample_id"]: sample
        for sample in (
            json.loads(line)
            for line in DATASET.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    failed_cases = [
        case for case in after["case_results"] if not case["rule_success"] or not case["final_success"]
    ]
    lines = [
        "# 阶段 3：Hybrid Parser 优化后报告",
        "",
        "> 本报告比较阶段3前后 Parser pipeline 行为。当前数据仍为 8 条 synthetic + 2 条淘宝脱敏 fixture，全部 `UNREVIEWED`；所有 accuracy 仅为机器一致性，不是人工真实准确率。",
        "",
        "## 1. 失败样本分析",
        "",
        f"阶段2规则层失败 {len(before['rule_failure_sample_ids'])} 条；阶段3后规则层失败 {len(after['rule_failure_sample_ids'])} 条。阶段3后 Hybrid 在 FakeLLMProvider 回放下失败 {len(after['hybrid_failure_sample_ids'])} 条。",
        "",
        "| sample_id | source | Bad Case | 规则 reason_code | 处理归属 | 阶段3后最终结果 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in failed_cases:
        sample = sample_metadata[case["sample_id"]]
        ambiguity_type = sample["ambiguity_type"]
        if ambiguity_type in {"title_noise", "multi_spec", "sku_mixed_text"}:
            owner = "LLM：语义商品身份/组合关系"
        elif ambiguity_type in {"multi_pack", "unit_ambiguity", "gift"}:
            owner = "RULE：数量/单位/赠品边界"
        else:
            owner = "按 reason_code 决定；当前样本需 LLM 复核"
        final_result = "PASS" if case["final_success"] else "FAIL/CLOSED"
        lines.append(
            f"| `{case['sample_id']}` | {case['source_type']} | `{ambiguity_type}` | `{case['rule_failure_reason']}` | {owner} | {final_result} |"
        )
    if not failed_cases:
        lines.append("| — | — | — | — | — | 无失败样本 |")
    lines += [
        "",
        "结论：当前两个失败均是淘宝标题噪声导致的商品核心名称语义问题，不用 sample_id 特判；规则层明确报告 `ambiguous_missing_primary_quantity`，Hybrid 才尝试结构化 LLM。数量、单位、赠品、组合等规则可处理字段未回退到 LLM。",
        "",
        "## 2. Pipeline 变化",
        "",
        "```text",
        "normalize",
        "  → candidate extraction",
        "  → deterministic parse",
        "  → ambiguity detection + reason_code",
        "  → optional structured LLM",
        "  → Pydantic schema validation",
        "  → confidence / parser_source / reason",
        "```",
        "",
        "新增可观测字段：`parser_source`（RULE / LLM / HYBRID）、`candidate_count`、`reason_code`、`reason`、`llm_schema_valid`、`llm_invocation_reason`。Malformed JSON、schema 不合法或 provider 异常均 fail closed，保留规则结果。",
        "",
        "## 3. 优化前后指标",
        "",
        "| 指标 | 优化前 | 优化后 | 解释 |",
        "| --- | ---: | ---: | --- |",
        f"| Rule overall accuracy | {before['rule_accuracy']['numerator']}/{before['rule_accuracy']['denominator']} ({before['rule_accuracy']['accuracy']:.4f}) | {_metric(after['metrics'], 'rule_accuracy')} | 规则层仍不猜测标题核心名 |",
        f"| Hybrid overall accuracy | {before['hybrid_accuracy']['numerator']}/{before['hybrid_accuracy']['denominator']} ({before['hybrid_accuracy']['accuracy']:.4f}) | {_metric(after['metrics'], 'hybrid_accuracy')} | FakeLLM fallback 回放 |",
        f"| Ambiguous accuracy | {before['ambiguous_accuracy']['numerator']}/{before['ambiguous_accuracy']['denominator']} ({before['ambiguous_accuracy']['accuracy']:.4f}) | {_metric(after['metrics'], 'hybrid_ambiguous_case_accuracy')} | 仅机器一致性 |",
        f"| LLM invocation rate | {before['llm_invocation_rate']['numerator']}/{before['llm_invocation_rate']['denominator']} ({before['llm_invocation_rate']['rate']:.4f}) | {_metric(after, 'llm_invocation_rate')} | 仅不确定样本调用 |",
        f"| Schema failure rate | {before['schema_failure_rate']['numerator']}/{before['schema_failure_rate']['denominator']} ({before['schema_failure_rate']['rate']:.4f}) | {_metric(after, 'schema_failure_rate')} | 失败时规则回退 |",
        "",
        "## 4. 验证与限制",
        "",
        "- 现有商品 Parser 测试增加了 pipeline、reason code、RULE/HYBRID source 和 malformed LLM fail-closed regression。",
        "- Evaluation runner 继续使用 FakeLLMProvider 验证路由和 schema 合约；它不是线上模型测试。",
        "- 当前没有 HUMAN_VERIFIED 样本，不能宣称真实商品识别准确率提升。",
        "- 淘宝样本是脱敏 fixture，不是实时淘宝页面结果。",
        "",
    ]
    AFTER_MD.write_text("\n".join(lines), encoding="utf-8")
    print(AFTER_MD)


if __name__ == "__main__":
    main()
