"""Evaluation source provenance and eligibility checks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from evaluation.schema import AnnotationStatus, HumanAnnotationRecord


ROOT = Path(__file__).resolve().parents[1]


def resolve_source_path(reference: str) -> Path | None:
    """Resolve a repository-relative source path and reject unsafe references."""

    reference_without_selector = reference.partition("#")[0]
    parsed = urlparse(reference_without_selector)
    if parsed.scheme or parsed.netloc:
        return None
    candidate = Path(reference_without_selector)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_annotation(annotation: HumanAnnotationRecord) -> dict[str, Any]:
    """Return an audit record without changing annotation status."""

    path = resolve_source_path(annotation.anonymized_source)
    errors: list[str] = []
    if path is None:
        errors.append("unsafe_or_non_repository_source_path")
    elif not path.is_file():
        errors.append("source_file_missing")

    actual_hash: str | None = None
    if path is not None and path.is_file():
        actual_hash = sha256_file(path)
        if not annotation.source_hash:
            errors.append("source_hash_missing")
        elif annotation.source_hash != actual_hash:
            errors.append("source_hash_mismatch")

    if annotation.source_type.value not in {"fixture", "real_anonymized", "synthetic"}:
        errors.append("invalid_source_type")
    if not annotation.source_hash:
        errors.append("source_hash_missing")
    if not annotation.source_format:
        errors.append("source_format_missing")
    if not annotation.source_platform:
        errors.append("source_platform_missing")
    elif annotation.source_platform != annotation.platform:
        errors.append("source_platform_mismatch")
    if annotation.source_redacted is not True:
        errors.append("source_not_marked_redacted")
    if annotation.annotation_status.value not in {
        "HUMAN_VERIFIED",
        "UNREVIEWED",
        "DISPUTED",
        "UNREVIEWED_SOURCE_MISSING",
        "REVIEW_REQUIRED",
    }:
        errors.append("invalid_annotation_status")

    eligible = (
        annotation.annotation_status is AnnotationStatus.HUMAN_VERIFIED
        and not errors
        and annotation.source_redacted is True
    )
    return {
        "sample_id": annotation.sample_id,
        "source_type": annotation.source_type.value,
        "annotation_status": annotation.annotation_status.value,
        "anonymized_source": annotation.anonymized_source,
        "repository_path": path.relative_to(ROOT).as_posix() if path is not None else None,
        "declared_hash": annotation.source_hash,
        "actual_hash": actual_hash,
        "source_format": annotation.source_format,
        "source_platform": annotation.source_platform,
        "provenance_origin": annotation.provenance_origin,
        "errors": errors,
        "human_metric_eligible": eligible,
    }
