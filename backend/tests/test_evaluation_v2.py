"""Evaluation v2 schema, replayability, and regression-gate tests."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.runner import DEFAULT_DATASET, DEFAULT_TAXONOMY, evaluate_dataset, load_dataset, replay_text


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
