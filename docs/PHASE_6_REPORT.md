# 阶段6报告——LLM Provider 与结构化 Agent Decision

更新时间：2026-08-08

## 范围

本阶段建立 provider-neutral LLM boundary 和有界 Agent Planner，实现 Workflow `NEEDS_AGENT_DECISION` 到一个结构化、fresh-grounded action 的通路。不连接真实购物平台，也不执行购买。

## 已实现

- `OpenAICompatibleProvider`、`AnthropicCompatibleProvider`，使用同步 `httpx` 和环境变量配置。
- `LLM_PROVIDER` provider factory，默认 `fake`，不需要 key 或网络。
- 有界 Agent Context，只包含目标、页面、压缩 observation、Workflow 状态、重要动作、约束和 retry budget。
- 严格 Pydantic `AgentDecision`、`AgentPlanResult` 状态处理。
- malformed output、invalid action、low confidence、provider error/retry 和确定性安全门。
- `AgentDecisionRouter` 只接受 `NEEDS_AGENT_DECISION`，重新绑定当前 observation ID，再交给 `ActionExecutor`。
- 使用 `httpx.MockTransport` 的离线 provider 契约测试。

## 验证

```text
uv run pytest
50 passed，1 个既有 Starlette/httpx warning
```

未发起 live provider 请求，仓库没有 API key、模型或 endpoint secret。

## 已知限制

- Provider 是协议适配器，不是 vendor SDK 集成，需要 endpoint-specific 配置。
- Agent 当前执行一个接受的动作；完整 resume/replan loop 延后实现。
- 尚无平台适配器、商品解析、价格比较、购买或支付实现。
- 低置信度/错误决策只在有界预算内拒绝或重试，不从自由文本提取动作。

## 完成判断

实现、离线 provider 契约、Planner/Router 测试、完整后端验证和配置文档均已完成，没有伪造 live-model 指标。
