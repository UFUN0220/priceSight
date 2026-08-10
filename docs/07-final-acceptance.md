# PriceSight 最终验收与冻结

## 验收结论

截至 2026-08-11，项目功能性调优冻结，最终评分 87/100，加权 86.85。评分沿用 2026-08-09 验收报告的八个维度和权重，没有为提高结果调整标准；最终定向补强后的远端 CI 已在 run `31413048761` 验证。

## 证据矩阵

| 范围 | 结果 | 证据边界 |
|---|---|---|
| Backend 全量 | VERIFIED | 172 passed |
| Python quality | VERIFIED | Ruff、mypy、compile、pre-commit、branch coverage 85% |
| Browser Mock Chromium | MOCK_RUNTIME_VERIFIED | Mock 页面闭环 |
| 淘宝 fixture | FIXTURE_VERIFIED | 脱敏 fixture replay |
| 淘宝公开只读 | LIVE_READONLY_VERIFIED | 140 links、45 displayed prices、无副作用 |
| Cross-platform adapters | FIXTURE_VERIFIED | Taobao/JD/Meituan fixture/Mock |
| Android Emulator Mock App | MOCK_RUNTIME_VERIFIED | 18 observations/actions、0 failed、0 timeout |
| Android 真实购物 App | NOT_VERIFIED | 未执行 |
| 生产性能 | NOT_VERIFIED | 未有生产负载证据 |

Final Remote Freeze：commit `7b201fec3def68de0a4be5eba1c63de8f35f7d9c` 的 `项目持续集成` run `31413048761` 由 `push` 触发，Python 测试与覆盖率、Python 质量门禁、Browser Mock Web E2E、Android client、Mock Shopping App 五个关键 job 全部成功。该 CI 结果不改变 HOLDOUT/HUMAN 评测指标。

## Evaluation

冻结数据 96 条，HUMAN_VERIFIED_ELIGIBLE 40 条；DEV 32 / HOLDOUT 8，seed `20260810`。`EXACT_CORE_V1` 为 DEV 5/32、HOLDOUT 0/8、ALL 16/96、Human 5/40；`EXACT_STRICT_V2` 为 DEV 2/32、HOLDOUT 0/8、ALL 12/96、Human 2/40。字段级人工指标为 quantity 26/40、specification 17/40、displayed price 10/37、effective price 0/12。泛化为 `LIMITED`。

正式 JSON 证据：

- [evaluation_final_freeze.json](../evaluation/reports/evaluation_final_freeze.json)
- [project_acceptance_freeze.json](../evaluation/reports/project_acceptance_freeze.json)
- [final_dataset_manifest.json](../evaluation/reports/final_dataset_manifest.json)

## 可发布与不可发布

可发布：Computer-Use Agent 工程闭环、Browser/Android Mock Runtime、安全停止、跨平台 Adapter、可复现 Evaluation/provenance 体系、公开网页只读 smoke evidence。

不可发布：真实购物 App 已验证、真实下单/支付能力、生产性能、全平台泛化准确率、FakeLLM 作为线上模型效果，以及未区分 split 的“85%识别准确率”。

## 后续建议

功能性优化保持冻结；如果继续工作，应先新增独立、人工确认且不泄漏的 holdout 数据，再评估是否值得修改 parser。不要围绕已有 8 条 holdout 反复调规则。
