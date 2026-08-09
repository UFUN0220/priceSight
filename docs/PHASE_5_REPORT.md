# 阶段5报告——YAML Workflow Engine

更新时间：2026-08-08

## 范围

本阶段在阶段4 Action Harness 之上增加确定性 YAML Workflow Engine，不调用 LLM，也不实现商品语义判断。

## 已实现

- `WorkflowLoader` 使用 `yaml.safe_load` 加载文本/文件，并用 Pydantic 校验。
- 将 `click`、`set_text` 等小写动作规范化为 `ActionType`。
- 校验非空 Workflow、唯一 step ID 和成功/失败路由。
- `WorkflowEngine` 顺序执行、转发 timeout、刷新 observation 并限制重试。
- 支持页面类型、必需文本和禁止文本 guard。
- 使用 fresh observation verifier 做期望状态验证。
- 支持 optional step、最小化成功/失败路由和 `NEEDS_AGENT_DECISION`。
- 支付/订单/安全页面和未 opt-in 购物车动作返回 `SAFETY_STOP`。
- 增加搜索、商品检查和默认安全的购物车示例 Workflow。
- `FakeActionDevice` 增加一次性拒绝，用于重试集成测试。

## 验证

```text
uv run pytest
39 passed，1 个既有 Starlette/httpx warning
```

示例 Workflow 已通过 loader 验证；未连接真实设备或购物应用。

## 已知限制

- 未连接后端 HTTP action channel 或物理 Android runtime。
- timeout 传递到 action boundary，严格 wall-clock 取消由 transport/device 层负责。
- 不自行选择歧义商品结果，下一阶段增加结构化 Agent Planner。
- 购物车 opt-in 默认 `False`，不存在购买或支付流程。

## 完成判断

实现、测试、示例 Workflow、完整后端验证和文档均已完成，没有伪造 benchmark 或任务成功率。
