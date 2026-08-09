# PriceSight 项目全面验收与整改复验报告

验收日期：2026-08-09
整改复验日期：2026-08-09

## 一、复验结论

综合评分由 **65/100 提升至 82/100**。

结论：**离线工程原型、桌面浏览器开发基线、淘宝脱敏结构 fixture 回放、Hybrid Parser、阶段5多平台 Adapter fixture 和阶段6设备会话可靠性验证通过；Android 双向 Runtime 因本机缺少 Emulator/AVD/system image 仍为 BLOCKED，实时淘宝/JD/美团网页能力和生产交付仍不通过。**

本轮已修复此前最关键的内部工程阻断项：后端开始保存设备最新观察并管理动作会话；Android Accessibility Service 已装配动作执行器，通过轮询接收动作并回传结构化结果；观察版本在入队和下发两个时点校验；Debug 构建允许访问本机 HTTP；仓库已有 Git 基线并新增 CI 工作流。

阶段 4 已完成 Android bridge 的 action_id 去重、lifecycle、指数退避/jitter/timeout/bounded retry 和 Mock/instrumented test harness，但本机没有 Emulator、AVD 或 Android 34 system image，Emulator 安装也未通过审批通道。因此 Android 仍只能归类为 `BUILD_ONLY`/`NOT_VERIFIED`，不能写成 Runtime Verified。桌面端已在本地 Chromium Mock Web 上完成真实浏览器 E2E；淘宝已完成专用 Adapter、脱敏结构 fixture 到 Observation 的转换和只读回放，但实时淘宝 DOM/ARIA 选择器仍未验证。

阶段 5 建立了统一 `PlatformAdapter`/`BasePlatformAdapter` 与 `NormalizedProduct`，Taobao、JD、Meituan 可沿 `Runtime → Observation → PlatformAdapter → NormalizedProduct → ComparisonEngine` 复用核心链路。JD/美团当前仅为脱敏 fixture Adapter 验证，不代表真实平台 selector 或实时网络验证。阶段 6 增加可替换 `SessionStore`、SQLite 持久化、动作租约、幂等和背压；不引入 Redis 或微服务。阶段 5/6 不改变 82/100 的整体评分，因为新增证据仍属于离线 fixture/mock/本地单体范围。

## 二、评分结果

| 维度 | 权重 | 整改前 | 整改后 | 说明 |
|---|---:|---:|---:|---|
| 需求覆盖与核心能力 | 15% | 78 | 92 | 增加 Browser Runtime、淘宝 Adapter、结构 fixture 回放和统一任务编排入口 |
| 架构与可解释性 | 15% | 84 | 94 | Runtime Port、Observation Parser、淘宝边界和 TaskOrchestrator 清晰 |
| 安全设计 | 15% | 80 | 90 | 浏览器 allowlist、订单确认停止和既有双重安全防线 |
| 测试与构建质量 | 15% | 74 | 88 | 最近一次已验证 131 个后端测试、淘宝 fixture 回放、浏览器 Runtime 测试和本地 Chromium E2E；Android instrumented runtime 仍未执行 |
| Evaluation 可信度 | 15% | 52 | 62 | 增加用户提供的脱敏淘宝结构 fixture 回放；仍无实时平台/人工复核指标 |
| 真实集成与运行就绪度 | 15% | 30 | 64 | 淘宝 Adapter 和只读 fixture 链路完成；Android Emulator runtime、实时 DOM/ARIA 和真实 Bad Case 仍缺失 |
| 工程治理与交付 | 5% | 20 | 68 | 增加浏览器 CI job；远端 Actions 和质量门槛仍待完善 |
| 文档与可沟通性 | 5% | 90 | 96 | 中文文档同步阶段15、16、淘宝 fixture 边界和运行方法 |
| **加权总分** | **100%** | **65** | **82** | 加权值约 81.70，四舍五入 |

## 三、本轮整改内容

### 1. 后端设备会话

- `/observations` 保存每个 `device_id` 的最新观察，并与共享事件传输实例衔接。
- `POST /devices/{device_id}/actions` 接收已规划动作，校验观察版本和安全状态后入队。
- `GET /devices/{device_id}/actions/next` 为 Android 提供有界轮询；无动作返回 HTTP 204。
- `POST /devices/{device_id}/action-results` 保存执行结果。
- `GET /devices/{device_id}` 返回最新观察、待执行动作和已完成动作计数。
- 动作下发前再次核对最新 `observation_id`，过期动作记录为 `STALE_OBSERVATION`，不会发送给设备。
- 支持可选 `X-Device-Token`，并限制 WebSocket 消息字符数。

当前会话存储是进程内实现，适用于本地开发，不是多实例生产队列。

### 2. Android 双向桥接

- Accessibility Service 已实例化 `AndroidActionExecutor` 和 `DeviceBridgeClient`。
- 客户端上传最新 Observation，并以 500ms 间隔轮询待执行动作。
- 支持 CLICK、SET_TEXT、SCROLL_FORWARD、SCROLL_BACKWARD、BACK、有限 WAIT 和 STOP。
- 执行前再次检查本机最新观察 ID，并回传 SUCCESS、ACTION_REJECTED、TARGET_NOT_FOUND、STALE_OBSERVATION 或 SAFETY_BLOCKED。
- 修复 Android 将 `bounds` 输出为对象、后端要求四元数组的协议不一致。
- 明文 HTTP 仅在 `src/debug/AndroidManifest.xml` 开启，release 清单未开放该策略。

### 2.1 阶段 4 Android Runtime 工程增强

- Backend `ActionRequest`/`DeviceActionCommand` 增加 `action_id`、`command_id` 和 lifecycle。
- 相同 action_id 重复入队返回原 command；重复 result callback 幂等处理。
- lifecycle 明确为 `QUEUED → DISPATCHED → EXECUTING → SUCCESS / FAILED / STALE / SAFETY_BLOCKED`。
- DeviceBridge 增加 exponential backoff、jitter、HTTP timeout、bounded retry 和最多 256 个 command ID 的重复执行保护。
- Mock App 增加 instrumented/UI test；Android Client 增加完整闭环 instrumented harness。
- 以上为代码和测试 harness 状态，不等于设备运行证据；当前 Runtime 状态见第 4 节和 [Android Runtime 报告](../evaluation/reports/android_runtime_validation.md)。

### 2.2.1 阶段 6 设备会话可靠性

- 建立 `SessionStore` 抽象，`InMemorySessionStore` 用于测试，`SQLiteSessionStore` 用于 development 默认本地持久化。
- 统一提供观察保存、最新观察读取、动作入队、lease、完成、失败和设备状态查询。
- 增加 lease timeout 恢复、retry count、action_id 幂等、队列上限/429 背压、断开设备不下发和 stale observation 清理。
- InMemory 与 SQLite 均覆盖两个消费者竞争同一动作；SQLite 还覆盖关闭后重建会话的恢复。
- 该实现仍是单体本地存储，不代表多实例高可用或分布式队列。详细结果见 [设备会话报告](../evaluation/reports/session_store_validation.md)。

### 2.2 Evaluation 与 Hybrid Parser

- Evaluation v2 已建立统一 schema、Bad Case taxonomy、人工标注指南和 JSON/Markdown runner。
- 当前 10 条样本全部 `UNREVIEWED`，其中 synthetic 8 条、淘宝脱敏 fixture 2 条，`HUMAN_VERIFIED=0`。
- 阶段 3 Parser 已明确规则优先、ambiguity detection、结构化 LLM fallback 和 fail-closed schema validation。
- 当前机器一致性结果：Rule `8/10`、Hybrid FakeLLM 回放 `10/10`、LLM invocation `4/10`、schema failure `0/4`；这些不是人工真实准确率。
- 两条淘宝标题噪声规则失败样本已列入 [Hybrid Parser 报告](../evaluation/reports/hybrid_parser_after_optimization.md)，没有使用 sample_id 特判。

### 3. 安全加固

- SafetyGuard 可识别空格、连字符和下划线分隔的高风险词，例如“支 付 密 码”和 `PAY-NOW`。
- 增加确认订单、确认下单等高风险词。
- 后端入队前检查观察文本和动作内容；Android 在执行命令前进行第二道高风险动作检查。
- STOP 不会被解释为可继续操作，而是返回 `SAFETY_BLOCKED`。

### 4. 工程治理

- 已确认 Git 基线：`f765139 feat: phase 14 completed`。
- 新增 `.github/workflows/ci.yml`，覆盖 Python 3.12 编译/pytest、Android Client 和 Mock App 的测试与 Debug APK 构建。
- `.env.example` 新增设备共享令牌和传输消息大小配置。

CI 文件已完成本地静态配置，但尚无远端 Actions 运行记录，因此不能声称云端 CI 已通过。

### 5. 桌面浏览器 Runtime

- `BrowserRuntime` 实现统一 `ActionDevice`，从 DOM/ARIA 节点生成 Observation。
- Playwright locator 优先，当前 bounds 仅作为最后回退；观察版本仍由统一 Action Harness 管理。
- 启动时绑定 allowed hosts，跨域导航会停止。
- `scripts/run_browser_mock.py` 已完成真实 Chromium Mock Web E2E：搜索、输入、打开商品、价格读取、进入订单确认边界和安全停止。

### 6. 淘宝 Adapter 与结构 fixture 回放

- 新增 `TaobaoPlatformAdapter`、显式淘宝域名 allowlist 和淘宝选择器契约。
- 接入用户提供的 `iphone17` 商品列表和页面结构脱敏 fixture。
- 页面结构可转换为统一 Observation，再经标准网页 Adapter 抽取 2 条商品。
- 回放报告明确记录 `real_page_accessed=false`、`external_side_effect=false`，不把 fixture 价格当作实时价格。
- 当前仍未验证淘宝实时 DOM/ARIA 选择器、登录态、加载态、弹窗和商品详情页。

### 7. 多平台 Adapter 架构

- `BasePlatformAdapter` 提供 `parse_products()`、`parse_product_detail()`、`normalize_product()` 和 `safety_boundary()`，保留原有 `extract_*` 兼容入口。
- `NormalizedProduct` 统一保留平台、标题、基础价、有效价、数量、规格、店铺、商品标识、置信度和抽取来源。
- 新增 `JdPlatformAdapter` 与 `MeituanPlatformAdapter`，均使用脱敏 fixture；没有复制 Runtime、Agent 或核心 Workflow。
- 比较引擎根据规格、数量、显式优惠后的有效单位价和置信度排序；无法计算单位价时不强行推荐。
- 阶段5定向测试 28 passed；全量后端测试 122 passed。详细证据见 [多平台 Adapter 验证报告](../evaluation/reports/multi_platform_adapter_validation.md)。

## 四、实际验证结果

| 验证项 | 结果 |
|---|---|
| 后端全量测试 | **131 passed，0 failed，1 warning** |
| Python 编译检查 | **通过**：`backend/app`、`backend/tests`、`evaluation`、`scripts` |
| 新增闭环与安全定向测试 | **15 passed** |
| 浏览器 Runtime/Parser 定向测试 | **2 passed** |
| Mock Web Chromium E2E | **通过**：价格 `10.90`，安全状态 `SAFETY_BLOCKED`，未提交订单 |
| 淘宝结构 fixture 回放 | **通过**：搜索词 `iphone17`，识别 2 条商品，价格均为 `5999.00`，无外部副作用 |
| Android Client | 历史 `test assembleDebug` **BUILD_ONLY**；阶段4修改后的重新构建/connectedAndroidTest 未完成 |
| Mock Shopping App | 历史 `test assembleDebug` **BUILD_ONLY**；instrumented/UI test 未在设备上执行 |
| Android Emulator / AVD | **BLOCKED**：无 `emulator.exe`、无 AVD、无 Android 34 system image |
| Android 双向 Runtime | **NOT_VERIFIED / BLOCKED**：未执行 observation upload → action poll → Accessibility execution → result callback |
| SessionStore 可靠性 | **通过**：InMemory/SQLite 租约、并发、幂等、背压、断开和 stale cleanup 定向测试 9 passed |
| Android action latency / success rate | **NOT_MEASURED / BLOCKED** |
| Git 空白错误检查 | `git diff --check` 无错误 |

唯一 Python 警告来自 FastAPI TestClient 依赖链的 Starlette/httpx 弃用提示。Android 构建仍提示 Gradle 10 弃用兼容问题和 SDK XML v4/v3 工具版本差异。

## 五、Evaluation 可信度

本轮新增的是用户提供的脱敏、结构化淘宝页面 fixture，不是实时网页采样，也没有人工标注声明。Evaluation v2 当前包含 8 条 synthetic 和 2 条淘宝 fixture，全部 `UNREVIEWED`、`HUMAN_VERIFIED=0`：Rule `8/10`、Hybrid FakeLLM 回放 `10/10`、LLM invocation `4/10`、schema failure `0/4`。阶段13另记录 5 个合成树 fixture 的平均节点保留率 0.5714；10 次相同 Mock E2E 的任务和动作成功率 1.0；本机 Mock E2E 平均延迟约 7.8086ms。阶段16另记录了 2 条淘宝 fixture 商品回放，但不生成真实平台准确率或实时延迟指标。

这些结果只能证明离线 runner 和受控流程可复现，不能证明真实购物平台准确率、真实设备延迟、Agent 泛化能力或生产吞吐。

## 六、剩余阻断项

### P0——真实平台验收阻断

1. 无实时淘宝 DOM/ARIA 选择器验证，也无 Meituan/JD 的真实平台 Adapter 运行；当前 JD/美团 Adapter 和淘宝 fixture 均属于脱敏/离线证据。
2. 无真实应用 Bad Case、弹窗、加载态、登录态和规格选择恢复验证。
3. Android 无物理设备或模拟器运行证据；本机 ADB 可用，但 Emulator、AVD 和 Android 34 system image 缺失，阶段4报告为 `BLOCKED`。

### P1——高可信质量阻断

1. CI 尚无远端执行记录；没有 coverage 门槛、lint、静态类型检查和 pre-commit。
2. Android instrumented/UI test harness 已新增，但未在 Emulator/Device 执行；当前设备桥接主要由代码、后端契约测试和历史 BUILD_ONLY 证据覆盖。
3. 设备共享令牌默认空值，仅适用于本机开发；没有设备注册、令牌轮换和多租户授权。
4. Android 尚未接入 WebSocket event client；当前 Android 桥接使用 polling，event 路径仍是后端基准实现。
5. SQLite 会话已具备本地持久化、租约和背压；多进程协调、跨机器故障转移和断线后的真实 Android 重连仍未验证。
6. Evaluation v2 已纳入淘宝脱敏 fixture，但数据仍小且没有 HUMAN_VERIFIED 样本。

### P2——持续优化

1. 消除 Gradle 10 和 SDK XML 工具链警告。
2. 解决 TestClient 弃用警告并加入覆盖率、Ruff/类型检查。
3. 在 Emulator/Device 可用后实测桥接退避、抖动、命令确认租约、dispatch/execution latency 和成功率。
4. 在真实设备条件下重新测量 polling/event 延迟、失败率和分位数。

## 七、最终判定

- **离线技术演示：通过。**
- **淘宝脱敏结构 fixture 只读回放：通过。**
- **Android 双向 Runtime：BLOCKED / NOT_VERIFIED；代码闭环和 harness 已完成，但没有 Emulator/AVD 运行证据。**
- **实时淘宝网页和真实跨平台比价能力：不通过/未完成。**
- **JD/美团 Adapter 合同与脱敏 fixture 比价：通过；真实平台运行：NOT_VERIFIED。**
- **生产上线：不通过。**

机器可读版本见 [project_acceptance_2026-08-09.json](../evaluation/reports/project_acceptance_2026-08-09.json)。
