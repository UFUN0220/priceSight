# 架构说明

## 当前阶段13边界

仓库包含 FastAPI 服务壳、离线后端领域骨架、Android Accessibility 客户端边界、Mock Shopping App 和可复现评估工具：

```text
用户目标
  ↓
Task Router
  ├── YAML Workflow
  └── Agent Planner
          ↓
     Action Harness
          ↓
  polling / event transport
          ↓
  Android Accessibility client
          ↓
 Observation Compression
          ↓
 fresh observation + verification
```

## 后端边界

- `core`：配置、日志、依赖、安全和领域异常。
- `observation`：Observation DTO、解析、压缩和序列化。
- `action`：Action DTO、目标匹配、执行、验证和 fake device。
- `workflow`：YAML 加载、有限状态执行、重试和路由。
- `agent` / `llm`：有界 Agent Context、结构化决策和 provider 抽象。
- `parser`：规则优先的商品、数量、规格、促销和价格解析。
- `platform`：通用 adapter、Mock adapter 和 fixture adapter。
- `comparison`：规格匹配、最终价计算、推荐和缓存使用。
- `transport`：保留 polling，增加 event queue 和 WebSocket ingress。
- `evaluation`：原始 benchmark、最终指标汇总和范围审计。

## 安全边界

Android 客户端只负责设备观察、动作执行、调试显示和传输。商品推理、Workflow、解析、比较和安全判断均在后端。订单提交、支付、密码、验证码、身份验证和安全控制绕过由确定性 SafetyGuard 阻断。

## 当前实现与未实现

阶段13已完成离线评估和文档固化，但不代表真实设备或真实平台支持。真实平台 selector、真实 Accessibility Tree、登录、网络、下单和支付仍未实现。

## 项目级验收发现的集成缺口

- Android `PriceSightAccessibilityService` 当前只通过 HTTP POST 导出 observation，没有 WebSocket event client。
- `AndroidActionExecutor` 已实现但没有在 service 中装配，也没有接收后端 action command 的通道。
- FastAPI `/observations` 当前只返回确认，不保存最新 observation 或驱动 Workflow/Agent。
- FastAPI 全局 `event_transport` 与 dependency container 不是同一实例，`TRANSPORT_MODE` 尚未形成真实应用运行闭环。

因此当前架构图表示目标职责和离线实现，不应解释为真实设备已完成端到端联通。详细验收见 [PROJECT_ACCEPTANCE_REPORT.md](PROJECT_ACCEPTANCE_REPORT.md)。
