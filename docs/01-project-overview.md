# PriceSight 项目概览

## 项目定位

PriceSight 是一个面向跨平台商品比较的 Computer-Use Agent 工程。它通过 BrowserRuntime 或 Android Runtime 获取经过压缩的 DOM / Accessibility Observation，由规则、Workflow 和 Agent 协同完成商品检索、规格识别、价格解析和安全范围内的比较。

项目重点不是电商后端，而是可解释、可回放、可验证的 GUI Agent 执行闭环。

## 核心链路

```text
用户目标
  -> TaskOrchestrator
  -> Runtime Port
  -> Observation normalization/compression
  -> PlatformAdapter
  -> Hybrid Parser / Agent
  -> Action grounding + SafetyGuard
  -> Runtime execution
  -> fresh observation + verification
  -> NormalizedProduct / Comparison
```

## 当前冻结状态

- Backend：172 passed；branch coverage 85%，门槛 80%。Final Remote Freeze run `31413048761` 的五个关键 job 全部成功。
- Browser Mock Chromium：MOCK_RUNTIME_VERIFIED。
- 淘宝脱敏 fixture：FIXTURE_VERIFIED；公开页面只读 smoke：LIVE_READONLY_VERIFIED。
- Android Emulator + Mock Shopping App external harness：MOCK_RUNTIME_VERIFIED；不代表真实购物 App。
- Evaluation：96 条回放样本，40 条 HUMAN_VERIFIED_ELIGIBLE；固定 DEV/HOLDOUT；泛化结论 LIMITED。
- 项目功能性调优已冻结，不把旧 synthetic、fixture 或 FakeLLM 结果写成真实线上准确率。

## 安全边界

默认 SAFE MODE。允许搜索、浏览、读取商品信息、选择规格和安全范围内的购物车操作；进入真实订单确认、支付、密码、验证码或身份验证页面必须停止。

更多信息见 [架构](ARCHITECTURE.md)、[最终验收](07-final-acceptance.md)、[安全说明](SAFETY.md) 和 [Evaluation](05-ai-evaluation.md)。
