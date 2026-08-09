"""Reproducible Evaluation v2 replay and metric calculation."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from app.llm.base import LLMResponse
from app.llm.fake import FakeLLMProvider
from app.parser.hybrid import HybridProductParser
from app.parser.models import ParseResult
from app.parser.price import PriceParser
from app.parser.product import ProductParser

from evaluation.schema import EvaluationSample, ExpectedQuantity, ParsedOutput, load_sample


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evaluation" / "datasets" / "evaluation_v2.jsonl"
DEFAULT_TAXONOMY = ROOT / "evaluation" / "bad_case_taxonomy.json"


def load_dataset(path: Path = DEFAULT_DATASET) -> list[EvaluationSample]:
    """Load and validate every JSONL record, preserving source order."""

    return [load_sample(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve_json_path(value: Any, path: str) -> Any:
    for token in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if token.startswith("["):
            value = value[int(token[1:-1])]
        else:
            value = value[token]
    return value


def resolve_fixture_reference(reference: str) -> Any:
    """Resolve a repository-relative JSON fixture and optional #path selector."""

    relative_path, _, selector = reference.partition("#")
    fixture_path = ROOT / relative_path
    value: Any = json.loads(fixture_path.read_text(encoding="utf-8"))
    return _resolve_json_path(value, selector) if selector else value


def replay_text(sample: EvaluationSample) -> str:
    """Convert one observation or structured fixture item into parser input text."""

    if sample.raw_observation is not None:
        for key in ("text", "raw_text", "title"):
            value = sample.raw_observation.get(key)
            if isinstance(value, str) and value.strip():
                return value
        raise ValueError(f"sample {sample.sample_id} has no text in raw_observation")

    if not sample.fixture_reference:
        raise ValueError(f"sample {sample.sample_id} has no replay source")
    item = resolve_fixture_reference(sample.fixture_reference)
    if not isinstance(item, dict) or not isinstance(item.get("title"), str):
        raise ValueError(f"fixture reference for {sample.sample_id} does not point to a product item")
    price = item.get("price")
    price_text = f" ¥{float(price):.2f}" if isinstance(price, (int, float)) else ""
    return item["title"] + price_text


def _quantity_output(quantity: Any) -> ExpectedQuantity | None:
    if quantity is None:
        return None
    return ExpectedQuantity(
        count=quantity.count,
        content_amount=quantity.content_amount,
        content_unit=quantity.content_unit.value if quantity.content_unit else None,
        container_unit=quantity.container_unit.value if quantity.container_unit else None,
    )


def output_from_result(result: ParseResult, text: str) -> ParsedOutput:
    price = PriceParser().parse(text)
    return ParsedOutput(
        product_name=result.product_identity.name,
        quantity=_quantity_output(result.specification.primary_quantity),
        spec={"package_type": result.specification.package_type},
        price=(
            {"amount": price.amount, "currency": price.currency, "price_kind": "displayed"}
            if price
            else None
        ),
        source=result.source.value,
        ambiguous=result.ambiguous,
        confidence=result.confidence,
    )


def _llm_response(sample: EvaluationSample, text: str) -> LLMResponse:
    quantity = sample.expected_quantity
    quantity_payload = None
    if quantity is not None:
        quantity_payload = {
            "raw_text": text,
            "count": quantity.count or 1,
            "content_amount": str(quantity.content_amount) if quantity.content_amount is not None else None,
            "content_unit": quantity.content_unit,
            "container_unit": quantity.container_unit,
            "confidence": 0.90,
        }
    product_name = sample.expected_product_name or text
    payload = {
        "product_name": product_name,
        "normalized_product_name": product_name.casefold(),
        "quantity": quantity_payload,
        "promotions": [],
        "confidence": 0.90,
        "reason_summary": "deterministic replay response; not live model performance",
    }
    return LLMResponse(provider="fake", content=json.dumps(payload, ensure_ascii=False))


def _quantity_equal(expected: ExpectedQuantity | None, actual: ExpectedQuantity | None) -> bool:
    if expected is None or actual is None:
        return expected is actual
    return expected == actual


def _spec_equal(sample: EvaluationSample, output: ParsedOutput) -> bool:
    expected = sample.expected_spec
    actual = output.spec
    return (expected.package_type if expected else None) == (actual.package_type if actual else None)


def _price_equal(sample: EvaluationSample, output: ParsedOutput) -> bool:
    expected = sample.expected_price
    actual = output.price
    if expected is None or actual is None:
        return expected is actual
    return expected.amount == actual.amount and expected.currency == actual.currency and expected.price_kind == actual.price_kind


def _full_equal(sample: EvaluationSample, output: ParsedOutput) -> bool:
    product_equal = (sample.expected_product_name or "").casefold() == (output.product_name or "").casefold()
    return product_equal and _quantity_equal(sample.expected_quantity, output.quantity) and _spec_equal(sample, output) and _price_equal(sample, output)


def _field_equal(sample: EvaluationSample, output: ParsedOutput, field: str) -> bool:
    if field == "quantity":
        return _quantity_equal(sample.expected_quantity, output.quantity)
    if field == "spec":
        return _spec_equal(sample, output)
    if field == "price":
        return _price_equal(sample, output)
    raise ValueError(f"unsupported metric field: {field}")


def _metric(numerator: int, denominator: int, basis: str) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "accuracy": numerator / denominator if denominator else None,
        "basis": basis,
    }


def _metric_for(
    samples: list[EvaluationSample],
    outputs: dict[str, ParsedOutput],
    predicate: Callable[[EvaluationSample], bool],
    comparator: Callable[[EvaluationSample, ParsedOutput], bool],
    basis: str,
) -> dict[str, Any]:
    eligible = [sample for sample in samples if sample.sample_id in outputs and predicate(sample)]
    numerator = sum(comparator(sample, outputs[sample.sample_id]) for sample in eligible)
    return _metric(numerator, len(eligible), basis)


def _coverage(samples: list[EvaluationSample]) -> list[dict[str, Any]]:
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_text(encoding="utf-8"))
    known = {sample.sample_id for sample in samples}
    result = []
    for case_type, entry in taxonomy.items():
        sample_ids = [sample_id for sample_id in entry["sample_ids"] if sample_id in known]
        result.append(
            {
                "ambiguity_type": case_type,
                "description": entry["description"],
                "sample_ids": sample_ids,
                "replayable": bool(sample_ids),
                "status": "REPRESENTED_REPLAYABLE" if sample_ids else "NOT_REPRESENTED",
            }
        )
    return result


def evaluate_dataset(dataset_path: Path = DEFAULT_DATASET, sample_ids: set[str] | None = None) -> dict[str, Any]:
    all_samples = load_dataset(dataset_path)
    samples = [sample for sample in all_samples if sample_ids is None or sample.sample_id in sample_ids]
    if not samples:
        raise ValueError("no evaluation samples selected")

    texts = {sample.sample_id: replay_text(sample) for sample in samples}
    rule_parser = ProductParser()
    rule_results = {sample.sample_id: rule_parser.parse(texts[sample.sample_id]) for sample in samples}
    responses = [
        _llm_response(sample, texts[sample.sample_id])
        for sample in samples
        if rule_results[sample.sample_id].ambiguous
    ]
    provider = FakeLLMProvider(responses)
    hybrid_parser = HybridProductParser(provider)
    hybrid_results = {sample.sample_id: hybrid_parser.parse(texts[sample.sample_id]) for sample in samples}

    rule_outputs = {
        sample.sample_id: output_from_result(rule_results[sample.sample_id], texts[sample.sample_id])
        for sample in samples
    }
    final_outputs = {
        sample.sample_id: output_from_result(hybrid_results[sample.sample_id], texts[sample.sample_id])
        for sample in samples
    }
    model_outputs = {
        sample.sample_id: final_outputs[sample.sample_id]
        for sample in samples
        if hybrid_results[sample.sample_id].source.value == "llm"
    }

    all_predicate = lambda _sample: True
    field_predicates = {
        "quantity": lambda sample: sample.expected_quantity is not None,
        "spec": lambda sample: sample.expected_spec is not None,
        "price": lambda sample: sample.expected_price is not None,
        "ambiguous_case": lambda sample: sample.ambiguity_type.value != "none",
    }
    outputs_by_parser = {"rule": rule_outputs, "llm": model_outputs, "hybrid": final_outputs}
    metrics: dict[str, Any] = {}
    for parser_name, outputs in outputs_by_parser.items():
        basis = {
            "rule": "all selected samples; deterministic rule parser",
            "llm": "samples where FakeLLMProvider fallback returned source=llm; not live model performance",
            "hybrid": "all selected samples; rule-first hybrid with FakeLLMProvider",
        }[parser_name]
        metrics[f"{parser_name}_accuracy"] = _metric_for(samples, outputs, all_predicate, _full_equal, basis)
        for field, predicate in field_predicates.items():
            comparator = _full_equal if field == "ambiguous_case" else lambda sample, output, field=field: _field_equal(sample, output, field)
            metrics[f"{parser_name}_{field}_accuracy"] = _metric_for(samples, outputs, predicate, comparator, basis)

    case_results = []
    for sample in samples:
        final_output = final_outputs[sample.sample_id]
        success = _full_equal(sample, final_output)
        case_results.append(
            {
                "sample_id": sample.sample_id,
                "source_type": sample.source_type.value,
                "annotation_status": sample.annotation_status.value,
                "replay_text": texts[sample.sample_id],
                "parser_output": rule_outputs[sample.sample_id].model_dump(mode="json"),
                "model_output": model_outputs[sample.sample_id].model_dump(mode="json") if sample.sample_id in model_outputs else None,
                "final_output": final_output.model_dump(mode="json"),
                "success": success,
                "failure_reason": None if success else "machine_output_does_not_match_current_expected_fields",
            }
        )

    status_counts = Counter(sample.annotation_status.value for sample in samples)
    source_counts = Counter(sample.source_type.value for sample in samples)
    return {
        "report_version": "evaluation_v2",
        "dataset": dataset_path.relative_to(ROOT).as_posix(),
        "dataset_count": len(samples),
        "source_type_counts": dict(sorted(source_counts.items())),
        "annotation_status_counts": dict(sorted(status_counts.items())),
        "human_verified_count": status_counts.get("HUMAN_VERIFIED", 0),
        "human_accuracy_claim_available": status_counts.get("HUMAN_VERIFIED", 0) > 0,
        "metric_interpretation": "当前数据未达到 HUMAN_VERIFIED 门槛；accuracy 仅表示机器输出与未复核期望字段的一致性，不是人工真实准确率。",
        "metrics": metrics,
        "bad_case_coverage": _coverage(samples) if sample_ids is None else [],
        "case_results": case_results,
        "legacy_claim_review": {
            "legacy_report": "evaluation/reports/phase7_product_parsing.json",
            "legacy_claim": "8 条 synthetic 样本上的 rule/hybrid 1.0",
            "accepted_as_real_accuracy": False,
            "reason": "历史样本均为 synthetic 且 not_human_reviewed，旧报告没有 numerator/denominator 和人工复核证据。",
        },
        "limitations": [
            "当前没有 HUMAN_VERIFIED 样本，因此不发布复杂商品识别的真实准确率。",
            "LLM 指标使用 FakeLLMProvider 的确定性回放，不代表任何线上模型表现。",
            "taxonomy 中尚无可靠样本的类别标记为 NOT_REPRESENTED，不编造覆盖率。",
            "淘宝数据来自脱敏 fixture 回放，不是实时淘宝数据。",
        ],
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Evaluation v2 评测报告",
        "",
        "> 本报告建立可复现评测框架，不把未人工复核样本或 Fake LLM 输出描述为真实平台准确率。",
        "",
        "## 结论",
        "",
        f"- 数据集：`{report['dataset']}`，共 {report['dataset_count']} 条。",
        f"- 来源：`{json.dumps(report['source_type_counts'], ensure_ascii=False)}`。",
        f"- 标注状态：`{json.dumps(report['annotation_status_counts'], ensure_ascii=False)}`。",
        f"- HUMAN_VERIFIED：{report['human_verified_count']}；人工真实准确率是否可发布：`{report['human_accuracy_claim_available']}`。",
        "- 淘宝样本是脱敏 fixture 回放，不是实时淘宝数据。",
        "",
        "## 指标（均含 numerator / denominator）",
        "",
        "| 指标 | numerator | denominator | accuracy | 口径 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, metric in report["metrics"].items():
        accuracy = "N/A" if metric["accuracy"] is None else f"{metric['accuracy']:.4f}"
        lines.append(f"| `{name}` | {metric['numerator']} | {metric['denominator']} | {accuracy} | {metric['basis']} |")
    lines += [
        "",
        "## Bad Case 覆盖",
        "",
        "| 类型 | 状态 | 可重放 sample_id |",
        "| --- | --- | --- |",
    ]
    for entry in report["bad_case_coverage"]:
        ids = ", ".join(f"`{item}`" for item in entry["sample_ids"]) or "—"
        lines.append(f"| `{entry['ambiguity_type']}` | {entry['status']} | {ids} |")
    lines += [
        "",
        "## 历史指标审计",
        "",
        f"旧报告的“{report['legacy_claim_review']['legacy_claim']}”不作为真实准确率：{report['legacy_claim_review']['reason']}",
        "",
        "## 单条重放",
        "",
        "```powershell",
        "uv run python scripts/run_evaluation_v2.py --sample-id gift-water",
        "```",
        "",
        "runner 默认重放全部样本，并同时生成 JSON 与本 Markdown 报告。",
        "",
        "## 限制与下一步",
        "",
    ]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines += [
        "- 下一步应优先补充经过双人复核的 real_anonymized / fixture 样本，再建立可发布的人工准确率基线。",
        "",
    ]
    return "\n".join(lines)
