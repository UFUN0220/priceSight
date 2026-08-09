# 阶段12报告——事件驱动传输、缓存与性能基准

更新时间：2026-08-08

## 范围

本阶段保留 polling 路径并增加效率工程。所有测试只使用 Fake Device 和脱敏 synthetic fixture，不连接物理 Android 设备或真实购物平台。

## 已实现

- 增加 `TRANSPORT_MODE=polling|event` 和 event stabilization 配置。
- `PollingTransport.wait_for_change()` 作为可测量基线。
- `EventDrivenTransport`：异步 observation queue、去抖/稳定化、变化过滤和 `AccessibilityEvent` envelope。
- FastAPI `/ws/transport` WebSocket 入口，同时保留 `/observations`。
- `OfferCache` 默认内存，可选本地 SQLite 持久化。
- `ComparisonResult` 记录 cache hit/miss/age、平台、店铺、商品和规格。
- 可重复 benchmark，保存原始延迟样本及任务/缓存指标。

## 验证

```text
后端：79 passed，1 个既有 Starlette/httpx 弃用警告
```

10 次 synthetic 运行中，polling 平均 1.8174 ms，event 平均 29.1859 ms；条件为 1 ms 模拟传递延迟和 1 ms 稳定化窗口。event 数据包含本机 Windows 调度开销，不是生产性能结论。

warm cache hit rate 为 1.0，Mock task success rate 为 1.0，平均 LLM calls/task 为 1.0，平均 steps/task 为 13.0。

## 限制

WebSocket 已完成契约测试但未接入真实 Android Accessibility timing；SQLite 是本地单进程方案；真实网络、设备、应用、模型延迟和真实平台成功率未测量。
