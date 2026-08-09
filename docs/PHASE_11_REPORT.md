# 阶段11报告——可靠性与 Harness 工程

更新时间：2026-08-08

## 范围

本阶段改进离线 Action Harness 的可靠性，不增加平台数量，不连接物理 Android 设备。

## 已实现

- `ActionTraceEvent` 记录 task/step、observation hash、动作类型、脱敏目标、匹配策略、置信度、结果、延迟、重试次数和 Bad Case。
- 重试前重新获取 observation，并重新绑定 action 的 observation ID。
- `RepetitionDetector` 检测相同 action 作用于相同 observation 的重复状态，返回 `REPLAN_REQUIRED`，Workflow 转为 `NEEDS_AGENT_DECISION`。
- Bad Case 分类：`TARGET_MISSING`、`DUPLICATE_TARGET`、`STALE_OBSERVATION`、`PAGE_TRANSITION_DELAY`、`UNEXPECTED_DIALOG`、`SPEC_AMBIGUITY`、`ACTION_NO_EFFECT`。
- 回归测试覆盖目标缺失、重复目标、瞬态拒绝、持续失败和稳定 reliability key。

## 验证

```text
后端：72 passed，1 个既有 Starlette/httpx 弃用警告
```

离线报告实际观察到 `TARGET_MISSING`、`DUPLICATE_TARGET` 和 `ACTION_NO_EFFECT`；持续失败案例在一次设备调用后触发重规划。

## 限制

报告只使用 Fake Device。真实页面转场、异常弹窗、规格歧义和生产级 trace 持久化仍未实现；真实平台支持未声称完成。
