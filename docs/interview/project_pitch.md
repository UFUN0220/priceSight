# PriceSight 项目介绍

## 30 秒

PriceSight 是一个安全模式的跨平台 Computer-Use Agent 原型。它把 Android Accessibility Tree 和浏览器 DOM/ARIA 统一成 Observation，用 Workflow + Agent 规划任务，经 target grounding、observation_id 校验和 SafetyGuard 后执行。项目同时实现了 BrowserRuntime、Android DeviceBridge、平台 Adapter、规则优先 Hybrid Parser 和可审计的人工离线 Evaluation。Android 当前是 Emulator + Mock App 验证，不声称真实购物 App 已验证。

## 2 分钟

这个项目解决的是 Agent 在购物界面中“看得懂、动得准、停得住”的工程问题，而不是简单抓取价格。Runtime 层提供 Browser 和 Android 两条执行路径；Observation 层压缩 DOM/Accessibility 信息，保留文本、可交互性、bounds 和层级；TaskOrchestrator 将稳定步骤交给 YAML Workflow，将商品选择、规格歧义和异常恢复交给结构化 Agent。

动作不会直接执行 LLM 自由文本，而是经过 schema、目标 grounding、当前 observation_id、SafetyGuard 和执行后 fresh observation 验证。旧页面动作会被拒绝，订单确认、支付、验证码和身份验证会触发安全停止。Android 通过 DeviceBridge polling、lease、retry 和 idempotency 与后端形成双向链路；External Harness 在 Emulator + Mock Shopping App 上验证了完整动作矩阵。

商品解析采用 Rule-first + structured LLM fallback：数量、单位、规格和明确价格优先走 deterministic parser，复杂语义才进入 LLM，schema 失败 fail closed。淘宝、JD、美团通过统一 Adapter 进入 NormalizedProduct 和 Comparison Engine。Evaluation 使用 provenance audit、人工复核、固定 DEV/HOLDOUT、Bad Case taxonomy 和字段级分母；当前 HOLDOUT exact=0/8，因此项目明确结论是 generalization LIMITED，而不是包装一个高准确率数字。

