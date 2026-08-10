"""Evaluation v2 schema, replayability, and regression-gate tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.runner import (
    DEFAULT_DATASET,
    DEFAULT_TAXONOMY,
    _quantity_equal,
    evaluate_dataset,
    load_dataset,
    replay_text,
)
from evaluation.schema import EvaluationSample, HumanAnnotationRecord


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "evaluation" / "datasets" / "evaluation_v2_regression_policy.json"


def test_evaluation_v2_samples_have_stable_replay_sources_and_no_fake_human_status() -> None:
    samples = load_dataset()
    assert len(samples) == 10
    assert len({sample.sample_id for sample in samples}) == len(samples)
    assert all(sample.annotation_status.value == "UNREVIEWED" for sample in samples)
    assert all(replay_text(sample) for sample in samples)
    assert {sample.source_type.value for sample in samples} == {"synthetic", "fixture"}


def test_every_represented_bad_case_can_be_replayed_individually() -> None:
    samples = {sample.sample_id for sample in load_dataset()}
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_text(encoding="utf-8"))
    represented = [sample_id for entry in taxonomy.values() for sample_id in entry["sample_ids"]]
    assert set(represented) <= samples
    for sample_id in represented:
        report = evaluate_dataset(DEFAULT_DATASET, {sample_id})
        assert report["dataset_count"] == 1
        assert report["case_results"][0]["sample_id"] == sample_id


def test_evaluation_v2_machine_consistency_regression_policy() -> None:
    report = evaluate_dataset()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert report["dataset_count"] == policy["dataset_count"]
    assert report["human_verified_count"] == 0
    for metric_name, threshold in policy["required_metrics"].items():
        metric = report["metrics"][metric_name]
        assert metric["denominator"] == threshold["denominator"]
        assert metric["numerator"] >= threshold["minimum_numerator"]


def test_ambiguous_case_accuracy_is_scoped_full_match_and_detection_is_separate() -> None:
    report = evaluate_dataset()
    metrics = report["metrics_by_scope"]["ALL"]

    assert metrics["hybrid_ambiguous_case_accuracy"] == metrics["hybrid_accuracy"]
    assert metrics["hybrid_ambiguous_detection_accuracy"]["denominator"] == 10
    assert metrics["hybrid_ambiguous_detection_accuracy"]["numerator"] == 0


def test_quantity_metric_compares_equivalent_base_units_without_relaxing_count_or_container() -> None:
    base_liters = EvaluationSample.model_validate(
        {
            "sample_id": "quantity-audit-a",
            "platform": "generic",
            "source_type": "fixture",
            "query": "油",
            "raw_observation": {"text": "油 4L"},
            "expected_quantity": {"count": 1, "content_amount": "4", "content_unit": "l", "container_unit": "bottle"},
        }
    ).expected_quantity
    base_milliliters = EvaluationSample.model_validate(
        {
            "sample_id": "quantity-audit-b",
            "platform": "generic",
            "source_type": "fixture",
            "query": "油",
            "raw_observation": {"text": "油 4000ml"},
            "expected_quantity": {"count": 1, "content_amount": "4000", "content_unit": "ml", "container_unit": "bottle"},
        }
    ).expected_quantity

    assert base_liters is not None and base_milliliters is not None
    assert _quantity_equal(base_liters, base_milliliters)


def test_phase3_failure_classification_keeps_taobao_title_noise_in_llm_scope() -> None:
    report = evaluate_dataset()

    assert report["rule_failure_sample_ids"] == [
        "taobao-iphone17-item-1",
        "taobao-iphone17-item-2",
    ]
    assert report["hybrid_failure_sample_ids"] == []
    assert report["llm_invocation_rate"]["numerator"] == 4
    assert report["llm_invocation_rate"]["denominator"] == 10
    taobao_cases = [
        case for case in report["case_results"] if case["sample_id"].startswith("taobao-")
    ]
    assert all(case["rule_success"] is False for case in taobao_cases)
    assert all(case["final_success"] is True for case in taobao_cases)


def test_human_verified_scope_is_not_available_when_queue_is_empty() -> None:
    report = evaluate_dataset()

    human_metrics = report["metrics_by_scope"]["HUMAN_VERIFIED_ONLY"]
    assert report["human_verified_count"] == 0
    assert human_metrics["hybrid_accuracy"]["numerator"] == 0
    assert human_metrics["hybrid_accuracy"]["denominator"] == 0
    assert human_metrics["hybrid_accuracy"]["accuracy"] == "NOT_AVAILABLE"
    assert human_metrics["llm_invocation_rate"]["accuracy"] == "NOT_AVAILABLE"
    assert report["metrics"]["llm_quantity_accuracy"]["accuracy"] == "NOT_AVAILABLE"


def test_human_annotation_queue_is_unreviewed_and_does_not_claim_human_data() -> None:
    queue = Path(__file__).resolve().parents[2] / "evaluation/datasets/human_annotations.jsonl"
    records = [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(records) >= 10
    assert all(record["annotation_status"] in {"UNREVIEWED", "HUMAN_VERIFIED", "DISPUTED"} for record in records)
    assert all(
        not (record["source_type"] == "synthetic" and record["annotation_status"] == "HUMAN_VERIFIED")
        for record in records
    )
    sample_ids = [record["sample_id"] for record in records]
    assert len(sample_ids) == len(set(sample_ids))


def test_synthetic_sample_cannot_be_marked_human_verified() -> None:
    with pytest.raises(ValidationError):
        HumanAnnotationRecord(
            sample_id="synthetic-human-forbidden",
            platform="generic",
            source_type="synthetic",
            anonymized_source="synthetic",
            query="测试",
            raw_text="测试商品",
            expected_product_name="测试商品",
            annotation_status="HUMAN_VERIFIED",
            annotator_notes="人工确认",
        )

    with pytest.raises(ValidationError):
        EvaluationSample(
            sample_id="synthetic-human-forbidden",
            platform="generic",
            source_type="synthetic",
            query="测试",
            raw_observation={"text": "测试商品"},
            expected_product_name="测试商品",
            annotation_status="HUMAN_VERIFIED",
        )


def test_disputed_annotation_is_not_in_human_verified_scope(tmp_path: Path) -> None:
    annotation_path = tmp_path / "annotations.jsonl"
    annotation_path.write_text(
        json.dumps(
            {
                "sample_id": "taobao-iphone17-item-1",
                "platform": "taobao",
                "source_type": "fixture",
                "anonymized_source": "fixture",
                "query": "iphone17",
                "product_title": "Apple/苹果 iPhone 17",
                "raw_text": "Apple/苹果 iPhone 17 ¥5999.00",
                "expected_spec": {"package_type": None, "notes": "无容量信息"},
                "expected_displayed_price": {"amount": "5999.00", "currency": "CNY", "price_kind": "displayed"},
                "expected_product_name": "Apple/苹果 iPhone 17",
                "ambiguity_type": "title_noise",
                "annotation_status": "DISPUTED",
                "annotator_notes": "两名标注人对商品核心名存在分歧",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = evaluate_dataset(annotations_path=annotation_path)

    assert report["human_verified_count"] == 0
    assert report["metrics_by_scope"]["HUMAN_VERIFIED_ONLY"]["hybrid_accuracy"]["accuracy"] == "NOT_AVAILABLE"
    assert report["annotation_status_counts"]["DISPUTED"] == 1


def test_human_verified_annotation_is_scored_only_after_explicit_confirmation(tmp_path: Path) -> None:
    annotation_path = tmp_path / "annotations.jsonl"
    annotation_path.write_text(
        json.dumps(
            {
                "sample_id": "taobao-iphone17-item-1",
                "platform": "taobao",
                "source_type": "fixture",
                "anonymized_source": "fixture",
                "query": "iphone17",
                "product_title": "Apple/苹果 iPhone 17",
                "raw_text": "Apple/苹果 iPhone 17 ¥5999.00",
                "expected_spec": {"package_type": None, "notes": "无容量信息"},
                "expected_displayed_price": {"amount": "5999.00", "currency": "CNY", "price_kind": "displayed"},
                "expected_product_name": "Apple/苹果 iPhone 17",
                "ambiguity_type": "title_noise",
                "annotation_status": "HUMAN_VERIFIED",
                "annotator_notes": "人工逐字段复核，第二名复核人确认一致",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = evaluate_dataset(annotations_path=annotation_path)

    human_metrics = report["metrics_by_scope"]["HUMAN_ANNOTATED"]
    assert report["human_verified_count"] == 1
    assert human_metrics["hybrid_accuracy"]["numerator"] == 1
    assert human_metrics["hybrid_accuracy"]["denominator"] == 1
    assert human_metrics["hybrid_accuracy"]["accuracy"] == 1.0
    assert human_metrics["hybrid_displayed_price_accuracy"]["numerator"] == 1
    assert human_metrics["hybrid_displayed_price_accuracy"]["denominator"] == 1
    assert human_metrics["hybrid_effective_price_accuracy"]["accuracy"] == "NOT_AVAILABLE"
    assert "not live model performance" in human_metrics["llm_accuracy"]["basis"]
    assert report["metrics_by_scope"]["HUMAN_VERIFIED_ELIGIBLE"]["hybrid_accuracy"]["accuracy"] == "NOT_AVAILABLE"


def test_human_failure_analysis_excludes_unreviewed_samples(tmp_path: Path) -> None:
    annotation_path = tmp_path / "annotations.jsonl"
    annotation_path.write_text(
        json.dumps(
            {
                "sample_id": "taobao-iphone17-item-1",
                "platform": "taobao",
                "source_type": "fixture",
                "anonymized_source": "fixture",
                "query": "iphone17",
                "product_title": "Apple/苹果 iPhone 17",
                "raw_text": "Apple/苹果 iPhone 17 ¥5999.00",
                "expected_spec": {"package_type": None, "notes": "无容量信息"},
                "expected_displayed_price": {"amount": "5999.00", "currency": "CNY", "price_kind": "displayed"},
                "expected_product_name": "故意不同的人工名称",
                "ambiguity_type": "title_noise",
                "annotation_status": "HUMAN_VERIFIED",
                "annotator_notes": "人工逐字段复核，保留用于失败分析测试",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = evaluate_dataset(annotations_path=annotation_path)

    assert report["human_failure_analysis"]
    assert all(item["sample_id"] == "taobao-iphone17-item-1" for item in report["human_failure_analysis"])


def test_human_source_audit_does_not_turn_missing_files_into_fixture_evidence(tmp_path: Path) -> None:
    annotation_path = tmp_path / "annotations.jsonl"
    annotation_path.write_text(
        json.dumps(
            {
                "sample_id": "taobao-iphone17-item-1",
                "platform": "taobao",
                "source_type": "fixture",
                "anonymized_source": "missing/fixture.json",
                "query": "iphone17",
                "raw_text": "Apple/苹果 iPhone 17 ¥5999.00",
                "expected_product_name": "Apple/苹果 iPhone 17",
                "annotation_status": "HUMAN_VERIFIED",
                "annotator_notes": "人工确认来源，但测试文件不存在",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = evaluate_dataset(annotations_path=annotation_path)

    audit = report["human_source_audit"]
    assert audit["human_verified_declared_count"] == 1
    assert audit["repository_source_files_present"] == 0
    assert audit["repository_source_files_missing"] == 1
    assert audit["missing_sample_ids"] == ["taobao-iphone17-item-1"]
    assert report["human_accuracy_claim_eligible"] is False


def test_same_text_with_different_sample_ids_has_same_parser_output(tmp_path: Path) -> None:
    dataset_path = tmp_path / "same-text.jsonl"
    records = []
    for sample_id in ("same-text-a", "same-text-b"):
        records.append(
            {
                "sample_id": sample_id,
                "platform": "generic",
                "source_type": "synthetic",
                "query": "比较可口可乐",
                "raw_observation": {"text": "可口可乐 330ml*6罐"},
                "expected_quantity": {"count": 6, "content_amount": "330", "content_unit": "ml", "container_unit": "can"},
                "expected_spec": {"package_type": None, "notes": None},
                "expected_product_name": "可口可乐",
                "ambiguity_type": "multi_pack",
                "annotation_status": "UNREVIEWED",
            }
        )
    dataset_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")

    report = evaluate_dataset(dataset_path)
    outputs = {case["sample_id"]: case["parser_output"] for case in report["case_results"]}

    assert outputs["same-text-a"] == outputs["same-text-b"]
