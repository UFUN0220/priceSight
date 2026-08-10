# PriceSight 当前阶段状态

更新时间：2026-08-11

## 当前状态

`TARGETED_REINFORCEMENT`：围绕真实性、价格证据、确定性 effective price 和 abstention 完成一轮最小补强；原有 DEV/HOLDOUT 与 metric contract 未改。本文只作为状态入口，不重复保存完整历史。

## 已完成能力

- Runtime Port、Observation compression、Action grounding、TaskOrchestrator、Workflow + Agent。
- BrowserRuntime + Mock Chromium E2E；淘宝脱敏 fixture replay；淘宝公开页面只读 smoke。
- Android Accessibility Service、DeviceBridge、observation_id 双校验、SessionStore、SafetyGuard。
- Android Emulator + Mock Shopping App External Harness：`MOCK_RUNTIME_VERIFIED`。
- Taobao/JD/Meituan Adapter 与 NormalizedProduct/Comparison Engine。
- Evaluation provenance、annotation schema、Bad Case taxonomy、固定 DEV/HOLDOUT 和 frozen metric contract。
- Quantity unit/pack/total normalization、price candidate evidence/ranking、Decimal `PricingEngine`、`UNRESOLVED`/`NEED_MORE_EVIDENCE` 状态和 Rule/Workflow/LLM 边界文档。

## 当前证据

- Backend：160 passed。
- 历史封板 CI：161 passed；本轮本地质量门禁：172 passed，branch coverage 85%，门槛 80%。本轮改动尚未声明远端 CI 已验证。
- Browser Mock：`MOCK_RUNTIME_VERIFIED`；Taobao fixture：`FIXTURE_VERIFIED`；Taobao live readonly：`LIVE_READONLY_VERIFIED`。
- Android Mock App：18 observations/actions、0 failed、0 timeout，`MOCK_RUNTIME_VERIFIED`。
- Evaluation：96 条样本，40 条 HUMAN_VERIFIED_ELIGIBLE，DEV 32 / HOLDOUT 8；HOLDOUT exact 0/8，泛化 `LIMITED`。
- 本轮 baseline → final：HUMAN CORE `5/40 → 5/40`、STRICT `2/40 → 2/40`、quantity `26/40 → 26/40`、specification `17/40 → 17/40`、displayed price `10/37 → 10/37`、effective price `0/12 → 0/12`；HOLDOUT CORE/STRICT 仍为 `0/8`。代码能力由新增定向回归和 evidence/abstention 测试证明，未修改答案或污染 HOLDOUT。
- 机器结果：[baseline.json](../evaluation/results/baseline.json)、[baseline.md](../evaluation/results/baseline.md)、[final.json](../evaluation/results/final.json)、[final.md](../evaluation/results/final.md)。
- Final acceptance：87/100，加权 86.85。
- CI_VERIFIED（2026-08-10）：run `31394430586` / commit `25c616d3b426376a46d0e8b45798fabd4c874075` 的 Python 测试 161 passed、分支覆盖率 86%，Python 质量、浏览器 Mock 和两个 Android 测试构建 job 全部成功；HUMAN_VERIFIED exact core 5/40、strict 2/40 回归断言通过。

## 未完成或不应外推

- 真实购物 Android App、真实下单/支付、验证码、生产吞吐和长期价格稳定性未验证。
- FakeLLM structured replay 不能称为线上模型效果。
- fixture、Mock 和 synthetic 结果不能合并为实时平台准确率。
- effective price 人工正确数为 0/12，仍需更多合法人工数据后再评估。

## 文档入口

- [文档索引](README.md)
- [开发历史](03-development-history.md)
- [测试与工程质量](04-testing-and-quality.md)
- [AI、Parser 与 Evaluation](05-ai-evaluation.md)
- [环境与复现](06-environment-and-setup.md)
- [最终验收](07-final-acceptance.md)
- [架构](ARCHITECTURE.md)
- [安全](SAFETY.md)
