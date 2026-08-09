# 阶段1报告——后端领域骨架

日期：2026-08-08

## 范围

本阶段建立后端契约和离线测试替身，不实现真实 LLM、Android Accessibility、YAML Workflow、购物平台、支付或下单。

## 已实现

- 配置、结构化日志、安全守卫、领域异常和依赖容器。
- Observation、Action、Workflow、Agent 的 Pydantic DTO。
- provider-neutral 的 `LLMProvider` 契约和离线 `FakeLLMProvider`。
- `DeviceTransport`、`FakeDevice` 和 `FakeTransport`。
- parser、platform、comparison、cache 包边界。

## 设计选择

默认使用 fake 实现，使测试不需要 API key、Android 设备或网络。DTO 使用 Pydantic 校验结构化数据；安全规则独立于 Prompt，并放在确定性代码中。领域包与 `main.py` 分离，便于后续增量实现。

## 验证

```text
uv run pytest
12 passed，1 warning
```

未调用外部 LLM，未连接 Android 设备，未访问真实购物应用。

## 已知限制

- LLM 目前仅有同步 fake 契约，没有网络 provider。
- Transport 目前仅有同步 fake 契约，没有 Android client。
- Action 仅是 DTO，尚无 grounding、执行、验证和重试。
- Workflow 仅是 DTO，尚无 YAML 加载和执行。
- Observation DTO 尚未压缩为 Accessibility Tree 表示。

## 下一阶段

阶段2：Kotlin Android Accessibility MVP。
