"""Create the immutable Phase 13 evaluation dataset manifest."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from evaluation.runner import load_dataset, load_human_annotations  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    dataset_path = ROOT / "evaluation/datasets/evaluation_v2.jsonl"
    annotations_path = ROOT / "evaluation/datasets/human_annotations.jsonl"
    provenance_path = ROOT / "evaluation/datasets/human_provenance.jsonl"
    split_path = ROOT / "evaluation/datasets/human_eval_split.json"
    taxonomy_path = ROOT / "evaluation/bad_case_taxonomy.json"
    contract_path = ROOT / "evaluation/METRIC_CONTRACT.md"
    output_path = ROOT / "evaluation/reports/final_dataset_manifest.json"

    samples = load_dataset(dataset_path, annotations_path)
    annotations = load_human_annotations(annotations_path)
    provenance = [
        json.loads(line)
        for line in provenance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    split = json.loads(split_path.read_text(encoding="utf-8"))
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    human_ids = [sample.sample_id for sample in samples if sample.annotation_status.value == "HUMAN_VERIFIED"]
    source_hashes: dict[str, dict[str, Any]] = {}
    for row in provenance:
        source_hashes[row["anonymized_source"]] = {
            "sha256": row["source_hash"],
            "source_platform": row["source_platform"],
            "provenance_origin": row["provenance_origin"],
        }
    manifest = {
        "manifest_version": "phase13_final_dataset_v1",
        "dataset_version": "evaluation_v2_frozen_with_human_overlay",
        "metric_contract_version": "v1_core_v2_strict",
        "dataset_file": "evaluation/datasets/evaluation_v2.jsonl",
        "dataset_sha256": sha256(dataset_path),
        "annotation_file": "evaluation/datasets/human_annotations.jsonl",
        "annotation_sha256": sha256(annotations_path),
        "provenance_file": "evaluation/datasets/human_provenance.jsonl",
        "provenance_sha256": sha256(provenance_path),
        "metric_contract_file": "evaluation/METRIC_CONTRACT.md",
        "metric_contract_sha256": sha256(contract_path),
        "sample_count": len(samples),
        "human_verified_eligible_count": len(human_ids),
        "annotation_status_counts": dict(Counter(sample.annotation_status.value for sample in samples)),
        "source_type_counts": dict(Counter(sample.source_type.value for sample in samples)),
        "human_sample_ids": human_ids,
        "dev_sample_ids": split["dev_sample_ids"],
        "holdout_sample_ids": split["holdout_sample_ids"],
        "split_seed": split["seed"],
        "source_hashes": source_hashes,
        "taxonomy": taxonomy,
        "human_annotation_count": len(annotations),
        "provenance_row_count": len(provenance),
        "freeze_rule": "Do not re-sample or alter expected labels to improve final metrics.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
