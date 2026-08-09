# 架构说明

## 当前桌面端扩展边界

仓库包含 FastAPI 服务壳、统一 Action/Workflow/Agent 后端、Android Accessibility Runtime、Playwright Browser Runtime、Mock Shopping App、Mock Web 和可复现评估工具：

```text
用户目标
  ↓
Task Router
  ├── YAML Workflow
  └── Agent Planner
          ↓
     Action Harness
          ↓
  Runtime Port
     ├── Android Accessibility client
     └── Playwright Browser Runtime
              ↓
 DOM / ARIA / Accessibility Observation
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
- `platform`：统一 `PlatformAdapter`/`BasePlatformAdapter`、Taobao Web Adapter、JD/Meituan 脱敏 fixture Adapter、Mock adapter 和标准化商品 DTO。
- `comparison`：规格匹配、最终价计算、推荐和缓存使用。
- `transport`：保留 polling，增加 event queue 和 WebSocket ingress。
- `runtime`：统一 Browser、Android 和 Mock 执行端；Browser Runtime 将 DOM/ARIA 节点归一化到统一 Observation，并复用 ActionExecutor。
- `task`：`TaskOrchestrator` 负责把 Workflow 运行在任意 `ActionDevice` 上，避免 Runtime 选择泄露到平台逻辑。
- `evaluation`：原始 benchmark、最终指标汇总和范围审计。

### 阶段 5 多平台 Adapter 链路

平台差异停留在 Adapter 层，统一链路为：

```text
Runtime
  → Observation
  → PlatformAdapter
  → NormalizedProduct
  → ComparisonEngine / Agent
```

`PlatformAdapter` 保留既有 `extract_*` 兼容入口，同时提供 `parse_products()`、`parse_product_detail()`、`normalize_product()` 和 `safety_boundary()`。比较引擎按规格、数量、显式优惠后的有效单位价和置信度做保守比较。JD/美团目前只完成脱敏 fixture 验证，不能解释为真实平台支持；详见 [阶段5报告](../evaluation/reports/multi_platform_adapter_validation.md)。

## 安全边界

Android 客户端只负责设备观察、动作执行、调试显示和传输。商品推理、Workflow、解析、比较和安全判断均在后端。订单提交、支付、密码、验证码、身份验证和安全控制绕过由确定性 SafetyGuard 阻断。

## 当前实现与未实现

阶段13已完成离线评估和文档固化，但不代表真实设备或真实平台支持。真实平台 selector、真实 Accessibility Tree、登录、网络、下单和支付仍未实现。

## 设备会话与动作闭环

本轮整改后，本地 polling 路径为：

```text
Android Accessibility Event
  → 压缩前稳定 DTO / Observation JSON
  → POST /observations?device_id=...
  → 后端保存设备最新 observation
  → Workflow / Agent 产生绑定 observation_id 的 ActionRequest
  → POST /devices/{device_id}/actions
  → 入队时安全与新鲜度检查
  → Android GET /actions/next
  → 下发时二次新鲜度检查
  → AndroidActionExecutor
  → POST /action-results
```

`DeviceSessionManager` 是进程内开发实现，负责最新观察、待执行动作和结果。Android `DeviceBridgeClient` 合并高频观察上传并每 500ms 轮询动作。Debug 清单允许连接 `10.0.2.2` 的明文开发服务，release 清单不开放该设置。

WebSocket event ingress 仍保留为后端事件基准，但 Android 当前未实现 WebSocket client。上述闭环已通过后端契约测试和 Android 编译构建，未在真实设备上运行，因此不应解释为真实平台端到端验收通过。详细结论见 [PROJECT_ACCEPTANCE_REPORT.md](PROJECT_ACCEPTANCE_REPORT.md)。

## 桌面浏览器闭环

浏览器路径不需要 Android HTTP polling：

```text
Browser Page
  → DOM/ARIA snapshot
  → BrowserObservationParser
  → Observation
  → TargetMatcher
  → BrowserRuntime
  → fresh Observation
```

`BrowserRuntime` 使用 Playwright locator、ARIA/文本和当前 bounds 执行动作；允许域名在启动时固定，导航离开 allowlist 会被停止。Playwright 是可选依赖，Mock Web E2E 位于 `scripts/run_browser_mock.py`。真实网站必须使用独立测试浏览器配置，用户手动登录，遇到 CAPTCHA、支付或订单提交立即停止。
