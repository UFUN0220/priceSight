# 阶段4报告——Action Grounding 与 Android Executor MVP

日期：2026-08-08

## 范围

本阶段建立从 typed action、fresh observation 匹配、设备执行到动作后验证的确定性 Action Harness。不连接真实购物应用、真实设备、LLM 或 Workflow Engine。

## 已实现

### 后端

- `ActionType`：点击、输入、前后滚动、返回、等待和停止。
- `ActionTarget`：resource ID、node ID、文本、content description、semantic hint 和 bounds。
- `TargetMatcher`：确定性匹配顺序和重复目标拒绝。
- `ActionVerifier`：fresh observation、页面和文本期望验证。
- `ActionExecutor`：安全门、stale observation 检查、设备分发、重新观察和显式结果状态。
- `FakeActionDevice`：内存测试设备。

### Android

`AndroidActionExecutor.kt` 从当前 `rootInActiveWindow` 解析节点路径，调用 `performAction()`；点击失败时使用当前 bounds 的 `dispatchGesture()` fallback，并支持输入、滚动和返回。

## 匹配契约

```text
resource ID
  → node ID
  → 精确文本/content description
  → 归一化文本
  → fuzzy candidate
  → 当前 observation 的 bounds
```

坐标不会来自缓存节点或旧 observation。`observation_id` 不一致时先返回 `STALE_OBSERVATION`。

## 验证

```text
后端：29 passed，1 warning
Android test：BUILD SUCCESSFUL
assembleDebug：BUILD SUCCESSFUL
```

Android 构建仍有非致命 Gradle 弃用和 SDK XML 兼容警告；未连接物理设备。

## 已知限制

- 后端 action boundary 仍是注入式 fake，没有 HTTP action channel。
- 尚无 retry/replan loop。
- 真实应用和设备运行行为尚未验证。

## 下一阶段

阶段5：YAML Workflow Engine。
