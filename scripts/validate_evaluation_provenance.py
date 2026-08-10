"""Validate replayable source provenance for human evaluation annotations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.provenance import audit_annotation  # noqa: E402
from evaluation.runner import DEFAULT_HUMAN_ANNOTATIONS, load_human_annotations  # noqa: E402
from evaluation.schema import AnnotationStatus  # noqa: E402


def validate(annotations_path: Path) -> dict[str, object]:
    records = load_human_annotations(annotations_path)
    audits = [
        audit_annotation(record)
        for record in records
        if record.annotation_status is AnnotationStatus.HUMAN_VERIFIED
    ]
    eligible = [row for row in audits if row["human_metric_eligible"]]
    failed = [row for row in audits if not row["human_metric_eligible"]]
    human_records = [record for record in records if record.annotation_status is AnnotationStatus.HUMAN_VERIFIED]
    ambiguity_counts: dict[str, int] = {}
    platform_counts: dict[str, int] = {}
    for record in human_records:
        ambiguity_counts[record.ambiguity_type.value] = ambiguity_counts.get(record.ambiguity_type.value, 0) + 1
        platform_counts[record.platform] = platform_counts.get(record.platform, 0) + 1
    bad_case_categories = len(ambiguity_counts)
    final_qualified = (
        len(eligible) >= 40
        and len(audits) > 0
        and len(failed) == 0
        and bad_case_categories >= 10
    )
    return {
        "annotations": annotations_path.as_posix(),
        "human_verified_count": len(audits),
        "source_audit_passed": len(eligible),
        "source_audit_failed": len(failed),
        "human_metric_eligible_count": len(eligible),
        "human_annotation_count": len(records),
        "new_human_samples_count": 0,
        "source_recreated_count": sum(
            row.get("provenance_origin") == "SOURCE_RECREATED_FROM_EXISTING_ANNOTATION" for row in audits
        ),
        "source_missing_count": sum("source_file_missing" in row.get("errors", []) for row in failed),
        "platform_counts": dict(sorted(platform_counts.items())),
        "ambiguity_counts": dict(sorted(ambiguity_counts.items())),
        "human_bad_case_categories": bad_case_categories,
        "final_qualified": final_qualified,
        "qualification_reasons": [
            f"eligible_human_samples={len(eligible)} (minimum=40)",
            f"source_audit_failed={len(failed)}",
            f"human_bad_case_categories={bad_case_categories} (minimum=10)",
        ],
        "human_metric_eligible": {row["sample_id"]: row["human_metric_eligible"] for row in audits},
        "audits": audits,
        "passed": not failed,
    }


def markdown_report(report: dict[str, object]) -> str:
    audits = report["audits"]
    assert isinstance(audits, list)
    qualification_reasons = report["qualification_reasons"]
    assert isinstance(qualification_reasons, list)
    lines = [
        "# Evaluation Provenance Final",
        "",
        "> 本报告只审计来源完整性和 Human metric eligibility，不调优 Parser，也不把重建 source 描述为原始网页 capture。",
        "",
        "## Existing 22 Samples",
        "",
        f"- HUMAN_VERIFIED declared：{report['human_verified_count']}",
        f"- SOURCE_RECREATED_FROM_EXISTING_ANNOTATION：{report['source_recreated_count']}",
        "- SOURCE_RECOVERABLE：0（本阶段未发现仓库内既有原始 capture）",
        f"- SOURCE_MISSING：{report['source_missing_count']}",
        f"- eligible：{report['human_metric_eligible_count']}",
        "- 重建 source 只包含 annotation 中已有的 query/title/raw_text，没有写入 expected、parser output 或人工标签。",
        "",
        "## New Human Samples",
        "",
        f"- 本阶段新增 HUMAN_VERIFIED：{report['new_human_samples_count']}",
        f"- 当前平台分布：`{json.dumps(report['platform_counts'], ensure_ascii=False)}`",
        f"- 当前 ambiguity 分布：`{json.dumps(report['ambiguity_counts'], ensure_ascii=False)}`",
        "- 新增人工数据入口：`evaluation/datasets/human_annotation_intake.jsonl`；所有模板默认 UNREVIEWED。",
        "",
        "## Audit",
        "",
        f"- total human annotation rows：{report['human_annotation_count']}",
        f"- source audit passed：{report['source_audit_passed']}",
        f"- source audit failed：{report['source_audit_failed']}",
        f"- HUMAN_VERIFIED_ELIGIBLE：{report['human_metric_eligible_count']}",
        "",
        "| sample_id | source | hash | eligible | errors |",
        "| --- | --- | --- | --- | --- |",
    ]
    for audit in audits:
        lines.append(
            f"| `{audit['sample_id']}` | `{audit['anonymized_source']}` | `{'OK' if audit['actual_hash'] == audit['declared_hash'] else 'MISMATCH'}` | "
            f"`{audit['human_metric_eligible']}` | `{', '.join(audit['errors']) or '—'}` |"
        )
    lines.extend(
        [
            "",
            "## Qualification",
            "",
            f"- final_qualified：`{report['final_qualified']}`",
            f"- reasons：`{'; '.join(str(reason) for reason in qualification_reasons)}`",
            "- 当前未达到 eligible_human_samples >= 40，因此不能将本阶段结果作为最终简历级人工准确率基线。",
            "",
            "## Parser Boundary",
            "",
            "Parser unchanged in this phase.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, default=DEFAULT_HUMAN_ANNOTATIONS)
    parser.add_argument("--json-report", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    args = parser.parse_args()
    report = validate(args.annotations)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_report:
        args.json_report.write_text(rendered + "\n", encoding="utf-8")
    if args.markdown_report:
        args.markdown_report.write_text(markdown_report(report), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
