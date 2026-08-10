# PriceSight 当前阶段状态

更新时间：2026-08-10

## 当前状态

`PROJECT_FREEZE`：功能性调优已结束，后续如继续工作，应建立新的、未泄漏的人工 holdout，再单独立项。本文只作为状态入口，不重复保存完整历史。

## 已完成能力

- Runtime Port、Observation compression、Action grounding、TaskOrchestrator、Workflow + Agent。
- BrowserRuntime + Mock Chromium E2E；淘宝脱敏 fixture replay；淘宝公开页面只读 smoke。
- Android Accessibility Service、DeviceBridge、observation_id 双校验、SessionStore、SafetyGuard。
- Android Emulator + Mock Shopping App External Harness：`MOCK_RUNTIME_VERIFIED`。
- Taobao/JD/Meituan Adapter 与 NormalizedProduct/Comparison Engine。
- Evaluation provenance、annotation schema、Bad Case taxonomy、固定 DEV/HOLDOUT 和 frozen metric contract。

## 当前证据

- Backend：160 passed。
- Branch coverage：85.69%，门槛 80%。
- Browser Mock：`MOCK_RUNTIME_VERIFIED`；Taobao fixture：`FIXTURE_VERIFIED`；Taobao live readonly：`LIVE_READONLY_VERIFIED`。
- Android Mock App：18 observations/actions、0 failed、0 timeout，`MOCK_RUNTIME_VERIFIED`。
- Evaluation：96 条样本，40 条 HUMAN_VERIFIED_ELIGIBLE，DEV 32 / HOLDOUT 8；HOLDOUT exact 0/8，泛化 `LIMITED`。
- Final acceptance：87/100，加权 86.85。
- CI 修复验证（2026-08-10）：统一人工标注路径后，Python 测试 161 passed，分支覆盖率 86%；GitHub Actions 重跑待确认。

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
