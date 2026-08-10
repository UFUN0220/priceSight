# PriceSight 简历指标审计

本文件只允许使用仓库已有证据。不要把 fixture、Mock、reconstructed source 或 FakeLLM 写成实时平台、生产或线上模型结果。

## SAFE_TO_USE

- 设计并实现安全模式的跨平台 Computer-Use Agent：统一 Observation、Workflow + Agent、Action Harness、SafetyGuard 和 Platform Adapter。
- 构建 Android Accessibility + Backend DeviceBridge 双向执行链路，并通过 Android Emulator + Mock Shopping App External Harness 验证 Observation、动作执行、结果回传、旧观察拒绝和安全阻断。
- 实现 BrowserRuntime，将 DOM/ARIA 转为 Observation，并完成淘宝公开网页只读 smoke；该 smoke 无登录、加购、下单或支付副作用。
- 设计 Rule-first + structured LLM fallback Hybrid Parser，并用 Pydantic/JSON Schema fail-closed 约束结构化输出。
- 建立带 provenance audit、人工复核、固定 DEV/HOLDOUT、Bad Case taxonomy 和逐字段 denominator 的离线 Evaluation。

## USE_WITH_CONTEXT

- Backend 160 tests、85.69% branch coverage：必须注明为本地测试/覆盖率，不是生产可靠性。
- Android Runtime `MOCK_RUNTIME_VERIFIED`：必须注明 Emulator + Mock Shopping App，不是真实购物 App 或物理设备。
- 淘宝 `LIVE_READONLY_VERIFIED`：必须注明一次公开页面只读 smoke，不代表登录态、长期 selector 稳定性或交易能力。
- HUMAN Evaluation：40 条人工复核 reconstructed anonymized samples；`EXACT_CORE_V1=5/40`、HOLDOUT=0/8，必须注明离线回放和 LIMITED generalization。
- Effective price：已实现 conservative contract 并有 regression tests，但 HUMAN_EVALUATION_NOT_ESTABLISHED，不能写成有效价格准确率。

## DO_NOT_USE

- 复杂商品识别准确率 85%。
- 50% → 85% 的准确率提升。
- 真实淘宝准确率、真实京东准确率、真实美团准确率。
- 线上 LLM accuracy。
- production latency、production throughput。
- physical-device verified。
- 已完成真实购物 App 自动下单、支付或生产级跨平台比价。
