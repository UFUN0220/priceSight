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
from evaluation.provenance import audit_annotation

from evaluation.schema import (
    AnnotationStatus,
    EvaluationSample,
    ExpectedQuantity,
    HumanAnnotationRecord,
    ParsedOutput,
    load_human_annotation,
    load_sample,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evaluation" / "datasets" / "evaluation_v2.jsonl"
DEFAULT_TAXONOMY = ROOT / "evaluation" / "bad_case_taxonomy.json"
DEFAULT_HUMAN_ANNOTATIONS = ROOT / "evaluation" / "datasets" / "human_annotations.jsonl"
DEFAULT_HUMAN_PROVENANCE = ROOT / "evaluation" / "datasets" / "human_provenance.jsonl"


def _read_jsonl(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_human_annotations(path: Path = DEFAULT_HUMAN_ANNOTATIONS) -> list[HumanAnnotationRecord]:
    """Load human annotations; an absent or empty work file is a valid empty queue."""

    provenance_by_id: dict[str, dict[str, Any]] = {}
    if path == DEFAULT_HUMAN_ANNOTATIONS and DEFAULT_HUMAN_PROVENANCE.exists():
        provenance_by_id = {
            row["sample_id"]: row
            for row in (json.loads(line) for line in _read_jsonl(DEFAULT_HUMAN_PROVENANCE))
        }
    records: list[HumanAnnotationRecord] = []
    for line in _read_jsonl(path):
        payload = json.loads(line)
        provenance = provenance_by_id.get(payload.get("sample_id"), {})
        payload.update(provenance)
        records.append(load_human_annotation(json.dumps(payload, ensure_ascii=False)))
    return records


def _annotation_has_labels(annotation: HumanAnnotationRecord) -> bool:
    return any(
        value is not None
        for value in (
            annotation.expected_quantity,
            annotation.expected_spec,
            annotation.expected_displayed_price,
            annotation.expected_effective_price,
            annotation.expected_product_name,
        )
    )


def _apply_human_annotations(
    samples: list[EvaluationSample], annotations: list[HumanAnnotationRecord]
) -> list[EvaluationSample]:
    by_id = {sample.sample_id: sample for sample in samples}
    for annotation in annotations:
        if annotation.sample_id in by_id:
            current = by_id[annotation.sample_id]
            if annotation.annotation_status is AnnotationStatus.UNREVIEWED and not _annotation_has_labels(annotation):
                continue
            if current.platform != annotation.platform or current.source_type != annotation.source_type:
                raise ValueError(f"annotation provenance does not match sample {annotation.sample_id}")
            by_id[annotation.sample_id] = current.model_copy(
                update={
                    "query": annotation.query,
                    "expected_quantity": annotation.expected_quantity,
                    "expected_spec": annotation.expected_spec,
                    "expected_price": annotation.expected_displayed_price,
                    "expected_displayed_price": annotation.expected_displayed_price,
                    "expected_effective_price": annotation.expected_effective_price,
                    "expected_product_name": annotation.expected_product_name,
                    "ambiguity_type": annotation.ambiguity_type,
                    "annotation_status": annotation.annotation_status,
                }
            )
            continue

        by_id[annotation.sample_id] = EvaluationSample(
            sample_id=annotation.sample_id,
            platform=annotation.platform,
            source_type=annotation.source_type,
            query=annotation.query,
            raw_observation={"text": annotation.raw_text, "title": annotation.product_title},
            expected_quantity=annotation.expected_quantity,
            expected_spec=annotation.expected_spec,
            expected_price=annotation.expected_displayed_price,
            expected_displayed_price=annotation.expected_displayed_price,
            expected_effective_price=annotation.expected_effective_price,
            expected_product_name=annotation.expected_product_name,
            ambiguity_type=annotation.ambiguity_type,
            annotation_status=annotation.annotation_status,
        )
    return list(by_id.values())


def load_dataset(
    path: Path = DEFAULT_DATASET, annotations_path: Path | None = None
) -> list[EvaluationSample]:
    """Load and validate every JSONL record, preserving source order."""

    samples = [load_sample(line) for line in _read_jsonl(path)]
    if annotations_path is not None:
        samples = _apply_human_annotations(samples, load_human_annotations(annotations_path))
    return samples


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


def _report_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _human_source_audit(
    samples: list[EvaluationSample], annotations: list[HumanAnnotationRecord]
) -> dict[str, Any]:
    """Audit whether HUMAN_VERIFIED rows have repository-replayable evidence.

    The annotation status is a human assertion and is never changed here.  This
    audit only reports whether the declared ``anonymized_source`` resolves to a
    file available in the repository, so a manually reviewed row cannot be
    mistaken for fixture or live-page evidence when its source artifact is absent.
    """

    annotation_by_id = {annotation.sample_id: annotation for annotation in annotations}
    human_samples = [sample for sample in samples if sample.annotation_status is AnnotationStatus.HUMAN_VERIFIED]
    rows: list[dict[str, Any]] = []
    for sample in human_samples:
        annotation = annotation_by_id.get(sample.sample_id)
        if annotation is None:
            rows.append(
                {
                    "sample_id": sample.sample_id,
                    "source_type": sample.source_type.value,
                    "anonymized_source": None,
                    "repository_path": None,
                    "errors": ["annotation_provenance_missing"],
                    "human_metric_eligible": False,
                }
            )
        else:
            rows.append(audit_annotation(annotation))

    failed = [row for row in rows if not row["human_metric_eligible"]]
    passed = [row for row in rows if row["human_metric_eligible"]]
    return {
        "human_verified_declared_count": len(rows),
        "source_audit_passed": len(passed),
        "source_audit_failed": len(failed),
        "repository_source_files_present": sum("source_file_missing" not in row.get("errors", []) for row in passed),
        "repository_source_files_missing": sum("source_file_missing" in row.get("errors", []) for row in failed),
        "missing_sample_ids": [row["sample_id"] for row in failed],
        "missing_sources": [row for row in failed],
        "eligible_sample_ids": [row["sample_id"] for row in passed],
        "source_rows": rows,
        "live_platform_evidence_count": 0,
        "synthetic_human_verified_count": sum(
            sample.source_type.value == "synthetic" for sample in human_samples
        ),
    }


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
        parser_source=result.parser_source.value,
        candidate_count=result.candidate_count,
        reason_code=result.reason_code,
        reason=result.reason,
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
    payload: dict[str, Any] = {
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
    expected = sample.expected_displayed_price or sample.expected_price
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
        "accuracy": numerator / denominator if denominator else "NOT_AVAILABLE",
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


def _metrics_for_scope(
    samples: list[EvaluationSample],
    rule_outputs: dict[str, ParsedOutput],
    model_outputs: dict[str, ParsedOutput],
    final_outputs: dict[str, ParsedOutput],
) -> dict[str, dict[str, Any]]:
    def all_predicate(_sample: EvaluationSample) -> bool:
        return True

    field_predicates = {
        "quantity": lambda sample: sample.expected_quantity is not None,
        "spec": lambda sample: sample.expected_spec is not None,
        "specification": lambda sample: sample.expected_spec is not None,
        "price": lambda sample: sample.expected_displayed_price is not None or sample.expected_price is not None,
        "displayed_price": lambda sample: sample.expected_displayed_price is not None or sample.expected_price is not None,
        "ambiguous_case": lambda sample: sample.ambiguity_type.value != "none",
    }
    outputs_by_parser = {"rule": rule_outputs, "llm": model_outputs, "hybrid": final_outputs}
    metrics: dict[str, dict[str, Any]] = {}
    for parser_name, outputs in outputs_by_parser.items():
        basis = {
            "rule": "selected samples in scope; deterministic rule parser",
            "llm": "selected samples where FakeLLMProvider fallback returned source=llm; not live model performance",
            "hybrid": "selected samples in scope; rule-first hybrid with FakeLLMProvider",
        }[parser_name]
        metrics[f"{parser_name}_accuracy"] = _metric_for(samples, outputs, all_predicate, _full_equal, basis)
        for field, predicate in field_predicates.items():
            comparator = (
                _full_equal
                if field == "ambiguous_case"
                else lambda sample, output, field=field: _field_equal(
                    sample,
                    output,
                    "spec" if field in {"specification"} else ("price" if field == "displayed_price" else field),
                )
            )
            metrics[f"{parser_name}_{field}_accuracy"] = _metric_for(samples, outputs, predicate, comparator, basis)
        metrics[f"{parser_name}_effective_price_accuracy"] = _metric(
            0,
            0,
            "NOT_AVAILABLE: current parser output exposes displayed price, not effective price",
        )
    return metrics


def _coverage(samples: list[EvaluationSample]) -> list[dict[str, Any]]:
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_text(encoding="utf-8"))
    known = {sample.sample_id for sample in samples}
    observed_by_type = {
        ambiguity_type: [sample.sample_id for sample in samples if sample.ambiguity_type.value == ambiguity_type]
        for ambiguity_type in {sample.ambiguity_type.value for sample in samples}
    }
    result = []
    for case_type, entry in taxonomy.items():
        taxonomy_ids = [sample_id for sample_id in entry["sample_ids"] if sample_id in known]
        sample_ids = list(dict.fromkeys(taxonomy_ids + observed_by_type.get(case_type, [])))
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


def evaluate_dataset(
    dataset_path: Path = DEFAULT_DATASET,
    sample_ids: set[str] | None = None,
    annotations_path: Path | None = None,
) -> dict[str, Any]:
    annotations = load_human_annotations(annotations_path) if annotations_path is not None else []
    all_samples = _apply_human_annotations(
        [load_sample(line) for line in _read_jsonl(dataset_path)], annotations
    )
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

    metrics = _metrics_for_scope(samples, rule_outputs, model_outputs, final_outputs)
    human_samples = [sample for sample in samples if sample.annotation_status is AnnotationStatus.HUMAN_VERIFIED]
    human_source_audit = _human_source_audit(samples, annotations)
    human_ids = {sample.sample_id for sample in human_samples}
    human_eligible_ids = set(human_source_audit["eligible_sample_ids"])
    human_eligible_samples = [sample for sample in human_samples if sample.sample_id in human_eligible_ids]
    human_annotated_metrics = _metrics_for_scope(
        human_samples,
        {sample_id: output for sample_id, output in rule_outputs.items() if sample_id in human_ids},
        {sample_id: output for sample_id, output in model_outputs.items() if sample_id in human_ids},
        {sample_id: output for sample_id, output in final_outputs.items() if sample_id in human_ids},
    )
    human_metrics = _metrics_for_scope(
        human_eligible_samples,
        {sample_id: output for sample_id, output in rule_outputs.items() if sample_id in human_ids},
        {sample_id: output for sample_id, output in model_outputs.items() if sample_id in human_ids},
        {sample_id: output for sample_id, output in final_outputs.items() if sample_id in human_ids},
    )

    case_results = []
    for sample in samples:
        final_output = final_outputs[sample.sample_id]
        rule_success = _full_equal(sample, rule_outputs[sample.sample_id])
        model_success = (
            _full_equal(sample, model_outputs[sample.sample_id])
            if sample.sample_id in model_outputs
            else None
        )
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
                "rule_success": rule_success,
                "model_success": model_success,
                "final_success": success,
                "rule_failure_reason": None if rule_success else rule_results[sample.sample_id].reason_code,
                "success": success,
                "failure_reason": None if success else "machine_output_does_not_match_current_expected_fields",
            }
        )

    status_counts = Counter(sample.annotation_status.value for sample in samples)
    source_counts = Counter(sample.source_type.value for sample in samples)
    llm_invocation_count = sum(result.llm_fallback_attempted for result in hybrid_results.values())
    llm_schema_failure_count = sum(result.llm_schema_valid is False for result in hybrid_results.values())
    rule_failure_ids = [
        sample.sample_id
        for sample in samples
        if not _full_equal(sample, rule_outputs[sample.sample_id])
    ]
    hybrid_failure_ids = [
        sample.sample_id
        for sample in samples
        if not _full_equal(sample, final_outputs[sample.sample_id])
    ]
    failure_analysis: list[dict[str, Any]] = []
    for sample in samples:
        expected_displayed_price = sample.expected_displayed_price or sample.expected_price
        expected_effective_price = sample.expected_effective_price
        expected = {
            "product_name": sample.expected_product_name,
            "quantity": sample.expected_quantity.model_dump(mode="json") if sample.expected_quantity else None,
            "specification": sample.expected_spec.model_dump(mode="json") if sample.expected_spec else None,
            "displayed_price": (
                expected_displayed_price.model_dump(mode="json")
                if expected_displayed_price is not None
                else None
            ),
            "effective_price": (
                expected_effective_price.model_dump(mode="json")
                if expected_effective_price is not None
                else None
            ),
        }
        for parser_name, output, success, parser_source, reason in (
            (
                "rule",
                rule_outputs[sample.sample_id],
                _full_equal(sample, rule_outputs[sample.sample_id]),
                rule_results[sample.sample_id].parser_source.value,
                rule_results[sample.sample_id].reason_code,
            ),
            (
                "hybrid",
                final_outputs[sample.sample_id],
                _full_equal(sample, final_outputs[sample.sample_id]),
                hybrid_results[sample.sample_id].parser_source.value,
                hybrid_results[sample.sample_id].reason_code,
            ),
        ):
            if not success:
                failure_analysis.append(
                    {
                        "sample_id": sample.sample_id,
                        "ambiguity_type": sample.ambiguity_type.value,
                        "parser": parser_name,
                        "expected": expected,
                        "actual": output.model_dump(mode="json"),
                        "parser_source": parser_source,
                        "failure_reason": reason,
                    }
                )
    error_by_type: list[dict[str, Any]] = []
    for ambiguity_type in sorted({sample.ambiguity_type.value for sample in samples}):
        typed = [sample for sample in samples if sample.ambiguity_type.value == ambiguity_type]
        human_typed = [sample for sample in human_samples if sample.ambiguity_type.value == ambiguity_type]
        error_by_type.append(
            {
                "ambiguity_type": ambiguity_type,
                "sample_count": len(typed),
                "human_verified_count": len(human_typed),
                "rule_error_count": sum(sample.sample_id in rule_failure_ids for sample in typed),
                "hybrid_error_count": sum(sample.sample_id in hybrid_failure_ids for sample in typed),
                "human_rule_error_count": sum(sample.sample_id in rule_failure_ids for sample in human_typed),
                "human_hybrid_error_count": sum(sample.sample_id in hybrid_failure_ids for sample in human_typed),
                "sample_ids": [sample.sample_id for sample in typed],
            }
        )
    human_failure_analysis = [
        failure for failure in failure_analysis if failure["sample_id"] in human_ids
    ]
    human_accuracy_available = status_counts.get(AnnotationStatus.HUMAN_VERIFIED.value, 0) > 0
    human_target_met = 40 <= len(human_eligible_samples) <= 60
    human_accuracy_claim_eligible = (
        human_target_met
        and human_source_audit["source_audit_failed"] == 0
        and human_source_audit["live_platform_evidence_count"] == 0
    )
    return {
        "report_version": "evaluation_v2_human_annotation_aware",
        "dataset": _report_path(dataset_path),
        "dataset_count": len(samples),
        "source_type_counts": dict(sorted(source_counts.items())),
        "platform_counts": dict(sorted(Counter(sample.platform for sample in samples).items())),
        "ambiguity_type_counts": dict(sorted(Counter(sample.ambiguity_type.value for sample in samples).items())),
        "human_verified_platform_counts": dict(sorted(Counter(sample.platform for sample in human_samples).items())),
        "human_verified_ambiguity_type_counts": dict(sorted(Counter(sample.ambiguity_type.value for sample in human_samples).items())),
        "annotation_status_counts": dict(sorted(status_counts.items())),
        "human_verified_count": status_counts.get("HUMAN_VERIFIED", 0),
        "human_accuracy_claim_available": human_accuracy_available,
        "human_accuracy_claim_eligible": human_accuracy_claim_eligible,
        "human_verified_target": {
            "minimum": 40,
            "maximum": 60,
            "met": human_target_met,
            "declared_human_verified": len(human_samples),
            "eligible_human_verified": len(human_eligible_samples),
            "additional_minimum_needed": max(0, 40 - len(human_eligible_samples)),
        },
        "human_source_audit": human_source_audit,
        "metric_interpretation": (
            "HUMAN_VERIFIED_ONLY 指标可计算，但当前样本规模或来源证据不足，不能作为线上总体真实准确率。"
            if human_accuracy_available
            else "HUMAN_VERIFIED=0；HUMAN_VERIFIED_ONLY 指标输出 NOT_AVAILABLE，当前只能发布机器一致性/fixture 回归。"
        ),
        "price_metric_definition": "displayed_price_accuracy compares expected_displayed_price; effective_price_accuracy is N/A because current parser output exposes displayed price only.",
        "llm_invocation_rate": _metric(llm_invocation_count, len(samples), "hybrid parser fallback invocations / selected samples"),
        "schema_failure_rate": _metric(llm_schema_failure_count, llm_invocation_count, "invalid structured LLM responses / LLM invocations"),
        "rule_failure_sample_ids": rule_failure_ids,
        "hybrid_failure_sample_ids": hybrid_failure_ids,
        "metrics": metrics,
        "metrics_by_scope": {
            "ALL": {
                **metrics,
                "llm_invocation_rate": _metric(llm_invocation_count, len(samples), "fallback invocations / ALL samples"),
                "schema_failure_rate": _metric(llm_schema_failure_count, llm_invocation_count, "invalid responses / ALL fallback invocations"),
            },
            "HUMAN_ANNOTATED": {
                **human_annotated_metrics,
                "llm_invocation_rate": _metric(
                    sum(hybrid_results[sample.sample_id].llm_fallback_attempted for sample in human_samples),
                    len(human_samples),
                    "fallback invocations / HUMAN_ANNOTATED samples",
                ),
                "schema_failure_rate": _metric(
                    sum(hybrid_results[sample.sample_id].llm_schema_valid is False for sample in human_samples),
                    sum(hybrid_results[sample.sample_id].llm_fallback_attempted for sample in human_samples),
                    "invalid responses / HUMAN_ANNOTATED fallback invocations",
                ),
            },
            "HUMAN_VERIFIED_ELIGIBLE": {
                **human_metrics,
                "llm_invocation_rate": _metric(
                    sum(hybrid_results[sample.sample_id].llm_fallback_attempted for sample in human_samples),
                    len(human_eligible_samples),
                    "fallback invocations / HUMAN_VERIFIED_ELIGIBLE samples",
                ),
                "schema_failure_rate": _metric(
                    sum(hybrid_results[sample.sample_id].llm_schema_valid is False for sample in human_eligible_samples),
                    sum(hybrid_results[sample.sample_id].llm_fallback_attempted for sample in human_eligible_samples),
                    "invalid responses / HUMAN_VERIFIED_ELIGIBLE fallback invocations",
                ),
            },
            "HUMAN_VERIFIED_ONLY": {
                **human_metrics,
                "llm_invocation_rate": _metric(
                    sum(hybrid_results[sample.sample_id].llm_fallback_attempted for sample in human_eligible_samples),
                    len(human_eligible_samples),
                    "fallback invocations / HUMAN_VERIFIED_ELIGIBLE samples",
                ),
                "schema_failure_rate": _metric(
                    sum(hybrid_results[sample.sample_id].llm_schema_valid is False for sample in human_eligible_samples),
                    sum(hybrid_results[sample.sample_id].llm_fallback_attempted for sample in human_eligible_samples),
                    "invalid responses / HUMAN_VERIFIED_ELIGIBLE fallback invocations",
                ),
            },
        },
        "bad_case_coverage": _coverage(samples) if sample_ids is None else [],
        "case_results": case_results,
        "failure_analysis": failure_analysis,
        "human_failure_analysis": human_failure_analysis,
        "error_by_ambiguity_type": error_by_type,
        "legacy_claim_review": {
            "legacy_report": "evaluation/reports/phase7_product_parsing.json",
            "legacy_claim": "8 条 synthetic 样本上的 rule/hybrid 1.0",
            "accepted_as_real_accuracy": False,
            "reason": "历史样本均为 synthetic 且 not_human_reviewed，旧报告没有 numerator/denominator 和人工复核证据。",
        },
        "limitations": [
            (
                "当前没有 HUMAN_VERIFIED 样本，因此 HUMAN_VERIFIED_ONLY 指标为 NOT_AVAILABLE，不发布复杂商品识别的真实准确率。"
                if not human_accuracy_available
                else f"HUMAN_VERIFIED_ONLY 当前有 {len(human_samples)} 条人工确认样本，但样本规模与来源仍不足以代表线上平台总体准确率。"
            ),
            "LLM 指标使用 FakeLLMProvider 的确定性回放，不代表任何线上模型表现。",
            "taxonomy 中尚无可靠样本的类别标记为 NOT_REPRESENTED，不编造覆盖率。",
            "淘宝数据来自脱敏 fixture 回放，不是实时淘宝数据。",
            (
                f"当前 HUMAN_VERIFIED 有 {human_source_audit['repository_source_files_missing']} 条记录的 anonymized_source 不存在于仓库，"
                "这些记录不能作为仓库内可回放 fixture 或实时页面证据。"
                if human_source_audit["repository_source_files_missing"]
                else "所有 HUMAN_VERIFIED 记录均有仓库内来源文件，但仍不等同于实时平台证据。"
            ),
            "只有 HUMAN_VERIFIED 数量达到 40–60 且来源文件审计通过，才可进入本项目最终人工准确率候选口径；仍不能外推为线上总体准确率。",
            "FakeLLMProvider 回放响应由评测 harness 构造，仅用于验证路由和 schema fail-closed，不可作为 LLM 真实准确率。",
            "effective_price_accuracy 当前为 N/A；Parser 输出没有可比较的 effective price 字段。",
        ],
    }


def markdown_report(report: dict[str, Any]) -> str:
    def accuracy_text(value: Any) -> str:
        if value == "NOT_AVAILABLE" or value is None:
            return "NOT_AVAILABLE"
        return f"{value:.4f}"

    def append_metric_table(lines: list[str], metrics: dict[str, Any]) -> None:
        lines.extend(
            [
                "| 指标 | numerator | denominator | accuracy | 口径 |",
                "| --- | ---: | ---: | --- | --- |",
            ]
        )
        for name, metric in metrics.items():
            lines.append(
                f"| `{name}` | {metric['numerator']} | {metric['denominator']} | "
                f"{accuracy_text(metric['accuracy'])} | {metric['basis']} |"
            )

    lines = [
        "# Evaluation v2 / Human-Verified 评测报告",
        "",
        "> 本报告建立可复现评测框架，不把未人工复核样本或 Fake LLM 输出描述为真实平台准确率。",
        "",
        "## 结论",
        "",
        f"- 数据集：`{report['dataset']}`，共 {report['dataset_count']} 条。",
        f"- 来源：`{json.dumps(report['source_type_counts'], ensure_ascii=False)}`。",
        f"- 标注状态：`{json.dumps(report['annotation_status_counts'], ensure_ascii=False)}`。",
        f"- HUMAN_VERIFIED：{report['human_verified_count']}；HUMAN_VERIFIED_ONLY 是否有可计算分母：`{report['human_accuracy_claim_available']}`；最终人工准确率候选资格：`{report['human_accuracy_claim_eligible']}`。",
        f"- 解释：{report['metric_interpretation']}",
        f"- 价格口径：{report['price_metric_definition']}",
        "- 淘宝样本是脱敏 fixture 回放，不是实时淘宝数据。",
        "",
        "## Dataset Composition",
        "",
        f"- total：{report['dataset_count']}；HUMAN_VERIFIED：{report['human_verified_count']}。",
        f"- source_type：`{json.dumps(report['source_type_counts'], ensure_ascii=False)}`。",
        f"- platform：`{json.dumps(report['platform_counts'], ensure_ascii=False)}`。",
        f"- ambiguity_type：`{json.dumps(report['ambiguity_type_counts'], ensure_ascii=False)}`。",
        f"- HUMAN_VERIFIED platform：`{json.dumps(report['human_verified_platform_counts'], ensure_ascii=False)}`。",
        f"- HUMAN_VERIFIED ambiguity_type：`{json.dumps(report['human_verified_ambiguity_type_counts'], ensure_ascii=False)}`。",
        "",
        "## Evidence Boundary",
        "",
        f"- 已声明 HUMAN_VERIFIED：{report['human_source_audit']['human_verified_declared_count']}。",
        f"- 仓库内来源文件存在：{report['human_source_audit']['repository_source_files_present']}；缺失：{report['human_source_audit']['repository_source_files_missing']}。",
        f"- 声明为 fixture 的人工样本：{sum(1 for row in report['human_source_audit']['source_rows'] if row['source_type'] == 'fixture')}；声明为 real_anonymized：{sum(1 for row in report['human_source_audit']['source_rows'] if row['source_type'] == 'real_anonymized')}。",
        f"- 可确认的实时平台证据：{report['human_source_audit']['live_platform_evidence_count']}；HUMAN_VERIFIED synthetic：{report['human_source_audit']['synthetic_human_verified_count']}。",
        "- FakeLLM 仅为 structured replay；本阶段没有线上 LLM 结果。",
        "- 结论：人工标签与来源证据分开记录。当前来源文件审计未通过，因此不能把这 22 条描述为仓库内可回放 fixture/真实页面数据，也不能发布真实平台总体准确率。",
        f"- 缺失来源 sample_id：{', '.join(f'`{item}`' for item in report['human_source_audit']['missing_sample_ids']) or '—'}。",
        "",
        "## ALL：所有可回放数据",
        "",
    ]
    append_metric_table(lines, report["metrics_by_scope"]["ALL"])
    lines += [
        "",
        "## HUMAN_VERIFIED_ONLY：仅人工明确确认的数据",
        "",
        "> 只有 `annotation_status == HUMAN_VERIFIED` 的样本进入本表；分母为 0 时统一输出 `NOT_AVAILABLE`。",
        "",
    ]
    append_metric_table(lines, report["metrics_by_scope"]["HUMAN_VERIFIED_ONLY"])
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
        "## 错误分析",
        "",
        "### 按 Bad Case 类型",
        "",
        "| ambiguity_type | sample_count | human_verified | rule_error_count | hybrid_error_count | human_rule_error | human_hybrid_error | sample_id |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for entry in report["error_by_ambiguity_type"]:
        lines.append(
            f"| `{entry['ambiguity_type']}` | {entry['sample_count']} | {entry['human_verified_count']} | "
            f"{entry['rule_error_count']} | {entry['hybrid_error_count']} | {entry['human_rule_error_count']} | "
            f"{entry['human_hybrid_error_count']} | {', '.join(f'`{item}`' for item in entry['sample_ids'])} |"
        )
    lines += [
        "",
        "### 失败样本明细",
        "",
        "| sample_id | ambiguity_type | parser | expected | actual | parser_source | failure_reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if report["failure_analysis"]:
        for failure in report["failure_analysis"]:
            lines.append(
                f"| `{failure['sample_id']}` | `{failure['ambiguity_type']}` | `{failure['parser']}` | "
                f"`{json.dumps(failure['expected'], ensure_ascii=False, separators=(',', ':'))}` | "
                f"`{json.dumps(failure['actual'], ensure_ascii=False, separators=(',', ':'))}` | "
                f"`{failure['parser_source']}` | `{failure['failure_reason']}` |"
            )
    else:
        lines.append("| — | — | — | — | — | — | 当前选择范围没有失败样本 |")
    lines += [
        "",
        "### HUMAN_VERIFIED 失败样本",
        "",
        "| sample_id | ambiguity_type | parser | expected | actual | parser_source | failure_reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if report["human_failure_analysis"]:
        for failure in report["human_failure_analysis"]:
            lines.append(
                f"| `{failure['sample_id']}` | `{failure['ambiguity_type']}` | `{failure['parser']}` | "
                f"`{json.dumps(failure['expected'], ensure_ascii=False, separators=(',', ':'))}` | "
                f"`{json.dumps(failure['actual'], ensure_ascii=False, separators=(',', ':'))}` | "
                f"`{failure['parser_source']}` | `{failure['failure_reason']}` |"
            )
    else:
        lines.append("| — | — | — | — | — | — | HUMAN_VERIFIED 没有失败样本 |")
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
        (
            "- 下一步应优先补充经过双人复核的 real_anonymized / fixture 样本，扩大人工准确率基线。"
            if report["human_verified_count"]
            else "- 下一步应优先补充经过双人复核的 real_anonymized / fixture 样本，再建立可发布的人工准确率基线。"
        ),
        "",
    ]
    return "\n".join(lines)
