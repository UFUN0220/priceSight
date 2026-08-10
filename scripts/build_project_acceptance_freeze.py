"""Build the Phase 13 project acceptance freeze artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DIMENSIONS: list[dict[str, Any]] = [
    {"name": "requirements_and_core", "weight": 15, "score": 93, "basis": "核心 Runtime、Observation、Workflow/Agent、Parser、Adapter、SessionStore 和安全模式均已实现并有回归；Android 为 Mock Runtime 证据。"},
    {"name": "architecture_and_explainability", "weight": 15, "score": 94, "basis": "Runtime Port、Observation、Adapter、Hybrid Parser、Comparison 和 SessionStore 职责分离，统一契约清晰。"},
    {"name": "safety", "weight": 15, "score": 92, "basis": "SafetyGuard、observation_id 双重校验、stale action 拒绝、订单确认停止和 Android/Browser 安全边界均有证据。"},
    {"name": "tests_and_builds", "weight": 15, "score": 92, "basis": "160 tests、85.69% branch coverage、Python quality gate、Android unit/build 和外部 Mock Harness 通过；Android lint 仍阻断。"},
    {"name": "evaluation_credibility", "weight": 15, "score": 72, "basis": "40 条 provenance-eligible 人工复核样本、固定 split、metric contract 和逐字段分母；source 为 reconstructed，HOLDOUT exact=0/8。"},
    {"name": "real_integration_readiness", "weight": 15, "score": 76, "basis": "淘宝公开网页只读 smoke 和 Android Emulator Mock Runtime 已验证；真实购物 App、JD/美团 live、物理设备仍未验证。"},
    {"name": "engineering_governance", "weight": 5, "score": 82, "basis": "Ruff、mypy、compile、pre-commit、coverage 和 diff gate 本地通过；远端 CI 无运行记录，Android lint 受离线依赖阻断。"},
    {"name": "documentation", "weight": 5, "score": 98, "basis": "最终验收、证据矩阵、metric contract、冻结 manifest、README 和面试材料均更新，明确限制与证据等级。"},
]


def main() -> None:
    evaluation = json.loads((ROOT / "evaluation/reports/evaluation_final_freeze.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "evaluation/reports/final_dataset_manifest.json").read_text(encoding="utf-8"))
    weighted = sum(item["score"] * item["weight"] / 100 for item in DIMENSIONS)
    report: dict[str, Any] = {
        "report_date": "2026-08-10",
        "assessment_revision": "phase13_project_freeze_metric_reconciled",
        "metric_contract_version": "v1_core_v2_strict",
        "overall_score": round(weighted),
        "weighted_score_before_rounding": weighted,
        "production_ready": False,
        "functional_optimization_frozen": True,
        "dimensions": DIMENSIONS,
        "evidence_matrix": {
            "LIVE_READONLY_VERIFIED": {
                "taobao_public_readonly_smoke": {
                    "report": "evaluation/reports/taobao_live_readonly_validation_final.json",
                    "real_page_accessed": True,
                    "items_extracted": 140,
                    "displayed_prices_extracted": 45,
                    "external_side_effect": False,
                }
            },
            "MOCK_RUNTIME_VERIFIED": {
                "android_emulator_mock_app_external_harness": {
                    "report": "evaluation/reports/android_runtime_validation_final.md",
                    "observation_count": 18,
                    "action_count": 18,
                    "failed": 0,
                    "timeout": 0,
                    "actions": ["CLICK", "SET_TEXT", "SCROLL_FORWARD", "BACK", "TARGET_NOT_FOUND", "STALE_OBSERVATION", "STOP", "SAFETY_BLOCKED"],
                },
                "browser_mock_chromium": {"report": "evaluation/reports/browser_runtime_validation.md", "safety_boundary": "SAFETY_BLOCKED"},
            },
            "FIXTURE_VERIFIED": {
                "taobao_jd_meituan_mock": {"reports": ["evaluation/reports/multi_platform_adapter_validation.md", "evaluation/reports/evaluation_v2.md"]}
            },
            "HUMAN_OFFLINE_EVALUATION": {
                "dataset_count": manifest["sample_count"],
                "human_verified_eligible": manifest["human_verified_eligible_count"],
                "provenance_passed": 40,
                "source_origin": "SOURCE_RECREATED_FROM_EXISTING_ANNOTATION",
                "report": "evaluation/reports/evaluation_final_freeze.md",
            },
            "BUILD_ONLY": {"android_client_assemble_debug": True, "mock_app_assemble_debug": True},
            "BLOCKED": {"android_lint": "offline cache missing com.android.tools.lint:lint-gradle:31.5.2"},
            "NOT_VERIFIED": [
                "real Taobao Android App",
                "real JD Android App",
                "real Meituan Android App",
                "physical Android device",
                "JD/Meituan live readonly smoke",
                "online LLM accuracy",
                "production throughput and latency",
                "remote CI run evidence",
            ],
        },
        "test_results": {
            "backend_pytest": {"passed": 160, "failed": 0},
            "branch_coverage_percent": 85.69,
            "coverage_fail_under": 80,
            "ruff": "passed",
            "mypy": "passed",
            "compile": "passed",
            "pre_commit": "passed",
            "git_diff_check": "passed",
            "android_unit_test": "passed",
            "android_assemble_debug": "passed",
            "mock_app_test": "passed",
            "mock_app_assemble_debug": "passed",
        },
        "evaluation": evaluation,
        "dataset_manifest": "evaluation/reports/final_dataset_manifest.json",
        "metric_contract": "evaluation/METRIC_CONTRACT.md",
        "limitations": [
            "HUMAN source 是 reconstructed anonymized source，不是原始网页 capture。",
            "HOLDOUT EXACT_CORE_V1 与 EXACT_STRICT_V2 均为 0/8，generalization=LIMITED。",
            "Effective price 已实现并有 regression tests，但 HUMAN_EVALUATION_NOT_ESTABLISHED。",
            "真实 Android shopping App、物理设备和 JD/美团 live 未验证。",
            "FakeLLM structured replay 不代表线上 LLM accuracy。",
        ],
    }
    json_path = ROOT / "evaluation/reports/project_acceptance_freeze.json"
    md_path = ROOT / "evaluation/reports/project_acceptance_freeze.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# PriceSight 项目封板验收报告",
        "",
        "验收日期：2026-08-10",
        "状态：PROJECT_FREEZE",
        "原则：功能性调优、Parser accuracy 调优和 Android 功能调优停止；后续只接受 bug/security/build fixes。",
        "",
        "## Final Score",
        "",
        f"- 八维加权评分：{round(weighted)}/100（weighted={weighted:.2f}）。沿用原验收报告权重，没有创建新的有利评分标准。",
        "",
        "| Dimension | Weight | Score | Evidence basis |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in DIMENSIONS:
        lines.append(f"| {item['name']} | {item['weight']}% | {item['score']} | {item['basis']} |")
    lines += [
        "",
        "## Metric Reconciliation",
        "",
        "- Phase 11 的 Hybrid exact 5/40 与 Phase 12 的 Hybrid exact 2/40 不能直接比较：Phase 12 引入了 effective price 约束。",
        "- 可比口径是 EXACT_CORE_V1：Human 5/40；阶段 12 新增的 EXACT_STRICT_V2：Human 2/40。两者均已冻结在 evaluation/METRIC_CONTRACT.md。",
        "- Frozen split：DEV=32、HOLDOUT=8；HOLDOUT 两种 exact 均为 0/8。generalization 保持 LIMITED。",
        "",
        "## Evidence Matrix",
        "",
        "| Evidence level | Verified scope | Boundary |",
        "| --- | --- | --- |",
        "| LIVE_READONLY_VERIFIED | 淘宝公开网页只读 smoke：140 商品链接、45 展示价格 | 一次公开页访问，无登录、点击、加购、订单或支付 |",
        "| MOCK_RUNTIME_VERIFIED | Android Emulator + Mock Shopping App External Harness；Browser Mock Chromium | 不等价于真实购物 App 或生产运行 |",
        "| FIXTURE_VERIFIED | Taobao/JD/Meituan/Mock fixture replay | 不等价于实时平台 |",
        "| HUMAN_OFFLINE_EVALUATION | 40 条人工复核 reconstructed anonymized samples，provenance 40/40 | 不等价于原始网页 capture 或线上总体准确率 |",
        "| BUILD_ONLY | Android Client、Mock App assembleDebug | 不证明 Runtime |",
        "| BLOCKED | Android lint | 离线缺少 lint-gradle 依赖 |",
        "| NOT_VERIFIED | 真实 Android App、物理设备、JD/美团 live、线上 LLM、生产吞吐、远端 CI | 当前没有足够证据 |",
        "",
        "## Test Results",
        "",
        "- Backend：160 passed，0 failed。",
        "- Branch coverage：85.69%，门槛 80%。",
        "- Ruff、mypy、compile、pre-commit、git diff --check：通过。",
        "- Android unit test、assembleDebug、Mock App test/build：通过。",
        "- Android External Harness：18 observations、18 actions、0 failed、0 timeout。",
        "",
        "## Evaluation",
        "",
        "详见 evaluation_final_freeze.md 和 final_dataset_manifest.json。",
        "",
        "| Scope | EXACT_CORE_V1 | EXACT_STRICT_V2 | Quantity | Specification | Displayed price | Effective price |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scope in ("DEV", "HOLDOUT", "ALL"):
        metrics = evaluation["scopes"][scope]["metrics"]

        def show(name: str) -> str:
            value = metrics[name]
            accuracy = value["accuracy"]
            shown = accuracy if isinstance(accuracy, str) else f"{accuracy:.2%}"
            return f"{value['numerator']} / {value['denominator']} = {shown}"

        lines.append(
            f"| {scope} | {show('hybrid_exact_core_v1_accuracy')} | {show('hybrid_exact_strict_v2_accuracy')} | "
            f"{show('hybrid_quantity_accuracy')} | {show('hybrid_specification_accuracy')} | "
            f"{show('hybrid_displayed_price_accuracy')} | {show('hybrid_effective_price_accuracy')} |"
        )
    lines += [
        "",
        "- HUMAN_VERIFIED_ONLY：CORE 5/40，STRICT 2/40，Quantity 26/40，Specification 17/40，Displayed price 10/37，Effective price 0/12。",
        "- FakeLLM invocation 29/40；schema failure 1/29。最后一条为 real_noise_003 的 20W，分类为 EXPECTED_FAIL_CLOSED，不是本阶段合法 Unit schema bug。",
        "- Effective price：IMPLEMENTED_WITH_REGRESSION_TESTS；HUMAN_EVALUATION_NOT_ESTABLISHED。不再以 0/12 为优化目标。",
        "",
        "## Android Runtime",
        "",
        "Android 状态为 MOCK_RUNTIME_VERIFIED：External Harness 已验证 CLICK、SET_TEXT、SCROLL_FORWARD、BACK、TARGET_NOT_FOUND、STALE_OBSERVATION、STOP、SAFETY_BLOCKED；Duplicate Action 为 CONTRACT_VERIFIED。真实淘宝/JD/美团 Android App 和物理设备为 NOT_VERIFIED。",
        "",
        "## Browser",
        "",
        "Browser Mock Chromium 为 MOCK_RUNTIME_VERIFIED；淘宝 fixture 为 FIXTURE_VERIFIED；淘宝公开网页只读 smoke 为 LIVE_READONLY_VERIFIED。三类证据不合并。",
        "",
        "## Limitations",
        "",
        "- Human source 全部为 reconstructed annotation source；不是原始网页 capture。",
        "- HOLDOUT exact=0/8，泛化结论为 LIMITED。",
        "- 未验证真实 Android shopping App、物理设备、JD/美团 live、线上 LLM accuracy、production latency/throughput 和远端 CI。",
        "- SQLite SessionStore 是本地单体持久化，不是生产级分布式故障转移。",
        "",
        "## Freeze Decision",
        "",
        "PriceSight functional optimization frozen.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
