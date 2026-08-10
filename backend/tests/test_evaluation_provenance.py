"""Provenance contract tests for human Evaluation eligibility."""

from __future__ import annotations

import hashlib
from pathlib import Path

import evaluation.provenance as provenance
from evaluation.provenance import audit_annotation, resolve_source_path
from evaluation.schema import HumanAnnotationRecord


def _annotation(source: str, status: str = "HUMAN_VERIFIED", source_hash: str | None = None) -> HumanAnnotationRecord:
    return HumanAnnotationRecord(
        sample_id="provenance-test",
        platform="taobao",
        source_type="fixture",
        anonymized_source=source,
        source_hash=source_hash,
        source_format="jsonl",
        source_platform="taobao",
        source_redacted=True,
        query="测试商品",
        raw_text="测试商品 1件",
        expected_product_name="测试商品",
        annotation_status=status,
        annotator_notes="人工复核测试记录",
    )


def test_missing_source_is_ineligible() -> None:
    audit = audit_annotation(_annotation("evaluation/sources/missing.json", source_hash="0" * 64))
    assert audit["human_metric_eligible"] is False
    assert "source_file_missing" in audit["errors"]


def test_outside_repository_path_is_rejected() -> None:
    assert resolve_source_path("../outside.json") is None
    assert resolve_source_path("C:/Users/Administrator/source.json") is None
    assert resolve_source_path("https://example.test/source.json") is None


def test_invalid_hash_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    source = tmp_path / "source.jsonl"
    source.write_text('{"text":"脱敏"}\n', encoding="utf-8")
    audit = audit_annotation(_annotation("source.jsonl", source_hash="0" * 64))
    assert audit["human_metric_eligible"] is False
    assert "source_hash_mismatch" in audit["errors"]


def test_source_modification_changes_hash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    source = tmp_path / "source.jsonl"
    source.write_text('{"text":"脱敏"}\n', encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_text('{"text":"修改"}\n', encoding="utf-8")
    audit = audit_annotation(_annotation("source.jsonl", source_hash=digest))
    assert audit["human_metric_eligible"] is False
    assert "source_hash_mismatch" in audit["errors"]


def test_unreviewed_is_excluded_even_with_valid_source() -> None:
    audit = audit_annotation(_annotation("evaluation/sources/missing.json", "UNREVIEWED"))
    assert audit["human_metric_eligible"] is False


def test_source_missing_human_verified_is_excluded() -> None:
    audit = audit_annotation(_annotation("evaluation/sources/missing.json"))
    assert audit["human_metric_eligible"] is False


def test_valid_human_source_is_eligible() -> None:
    source = Path("evaluation/sources/taobao/human_verified_recreated.jsonl")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    audit = audit_annotation(_annotation(source.as_posix(), source_hash=digest))
    assert audit["human_metric_eligible"] is True
