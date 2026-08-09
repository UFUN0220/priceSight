# 阶段 6：设备会话可靠性与轻量持久化验证报告

验证日期：2026-08-09  
结论：**VERIFIED（InMemory 与 SQLite 会话逻辑）/ MOCK_VERIFIED（并发与 API 契约）**。

## 1. 设计结论

项目保持单体/模块化结构，没有引入 Redis、消息队列或微服务。`DeviceSessionManager` 继续负责观察版本校验和安全检查，存储职责下沉到可替换的 `SessionStore`：

```text
DeviceSessionManager
  ├── SafetyGuard
  └── SessionStore
        ├── InMemorySessionStore（测试）
        └── SQLiteSessionStore（development 默认）
```

`SessionStore` 明确提供：

- `save_observation`
- `get_latest_observation`
- `enqueue_action`
- `lease_next_action`
- `complete_action`
- `fail_action`
- `get_device_state`

## 2. 可靠性能力

- **Action lease**：动作下发获得 `lease_id` 和 `leased_until`，不再因为出队而永久丢失。
- **Lease timeout**：租约过期后回到 `QUEUED`，`retry_count` 加一；超过上限后进入 `FAILED/RETRY_EXHAUSTED`。
- **Idempotency**：同一设备的 `action_id` 只能对应一个 command；已完成动作再次入队不会再次执行；重复结果回调幂等。
- **Queue backpressure**：默认每设备最多 32 个活动动作，满队列抛出 `SessionQueueFullError`，HTTP 层返回 429。
- **Disconnected device**：设备最后一次观察超过 `SESSION_DEVICE_TIMEOUT_SECONDS` 后视为断开，不再 lease 新动作；恢复上传观察后可继续。
- **Stale cleanup**：lease 前重新检查最新 `observation_id`；过期动作记录 `STALE_OBSERVATION`，永不下发。
- **Concurrency**：InMemory 使用 `RLock`；SQLite 使用单连接锁与 `BEGIN IMMEDIATE`，两个消费者不能同时获得同一动作。

## 3. 持久化边界

development 默认使用 `data/device_sessions.sqlite3`，目录已加入 `.gitignore`。测试通过 `backend/tests/conftest.py` 显式切换到 InMemory，保证测试不依赖上一次运行残留；SQLite 持久化由临时数据库测试覆盖。

这不是分布式队列，也没有宣称多实例高可用。SQLite 适合当前本地单体开发和可复现演示；若未来需要多实例部署，应另行设计租约、数据库连接池和设备注册机制，不能把当前实现描述为生产级分布式调度。

## 4. 验证结果

### VERIFIED

- Python compileall：通过。
- 后端全量测试：`131 passed, 0 failed, 1 warning`。
- `git diff --check`：通过。

### MOCK_VERIFIED

- 阶段6会话可靠性定向测试：`9 passed`。
- 覆盖两个消费者竞争、SQLite 两消费者竞争、完成后不重复 lease、lease timeout 恢复、retry count、stale observation、队列上限、断开设备和 SQLite 重启恢复。
- 既有设备 API 和旧版 `DeviceSessionManager` 测试保持通过。

### BUILD_ONLY

- 本阶段未修改 Android 客户端桥接代码，Android 构建/Runtime 结论沿用阶段4：Runtime 仍为 BLOCKED，APK build 不能替代设备运行验证。

### NOT_VERIFIED

- 多进程 SQLite 高并发压测；
- Redis/云数据库/多实例部署；
- 真实 Android 断网、重连和进程崩溃恢复；
- 生产级吞吐、P99 延迟和跨机器故障转移。
