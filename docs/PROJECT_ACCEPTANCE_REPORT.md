# PriceSight 项目全面验收与整改复验报告

验收日期：2026-08-09
整改复验日期：2026-08-09

## 一、复验结论

综合评分由 **65/100 提升至 82/100**。

结论：**离线工程原型、桌面浏览器开发基线和淘宝脱敏结构 fixture 回放通过；实时淘宝网页能力和生产交付仍不通过。**

本轮已修复此前最关键的内部工程阻断项：后端开始保存设备最新观察并管理动作会话；Android Accessibility Service 已装配动作执行器，通过轮询接收动作并回传结构化结果；观察版本在入队和下发两个时点校验；Debug 构建允许访问本机 HTTP；仓库已有 Git 基线并新增 CI 工作流。

由于本轮按用户要求不连接物理设备，Android 双向闭环只完成代码、契约测试和 APK 构建验证。桌面端已在本地 Chromium Mock Web 上完成真实浏览器 E2E；淘宝已完成专用 Adapter、脱敏结构 fixture 到 Observation 的转换和只读回放，但实时淘宝 DOM/ARIA 选择器仍未验证。

## 二、评分结果

| 维度 | 权重 | 整改前 | 整改后 | 说明 |
|---|---:|---:|---:|---|
| 需求覆盖与核心能力 | 15% | 78 | 92 | 增加 Browser Runtime、淘宝 Adapter、结构 fixture 回放和统一任务编排入口 |
| 架构与可解释性 | 15% | 84 | 94 | Runtime Port、Observation Parser、淘宝边界和 TaskOrchestrator 清晰 |
| 安全设计 | 15% | 80 | 90 | 浏览器 allowlist、订单确认停止和既有双重安全防线 |
| 测试与构建质量 | 15% | 74 | 88 | 101 个后端测试、淘宝 fixture 回放、2 个浏览器 Runtime 测试和本地 Chromium E2E |
| Evaluation 可信度 | 15% | 52 | 62 | 增加用户提供的脱敏淘宝结构 fixture 回放；仍无实时平台/人工复核指标 |
| 真实集成与运行就绪度 | 15% | 30 | 64 | 淘宝 Adapter 和只读 fixture 链路完成；实时 DOM/ARIA 和 Bad Case 仍缺失 |
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

## 四、实际验证结果

| 验证项 | 结果 |
|---|---|
| 后端全量测试 | **101 passed，0 failed，1 warning，0.55s** |
| Python 编译检查 | **通过**：`backend/app`、`backend/tests`、`evaluation`、`scripts` |
| 新增闭环与安全定向测试 | **15 passed** |
| 浏览器 Runtime/Parser 定向测试 | **2 passed** |
| Mock Web Chromium E2E | **通过**：价格 `10.90`，安全状态 `SAFETY_BLOCKED`，未提交订单 |
| 淘宝结构 fixture 回放 | **通过**：搜索词 `iphone17`，识别 2 条商品，价格均为 `5999.00`，无外部副作用 |
| Android Client | **BUILD SUCCESSFUL**；`test assembleDebug`，64 个任务 |
| Mock Shopping App | **BUILD SUCCESSFUL**；`test assembleDebug`，64 个任务 |
| Android Client Debug APK | 已生成，845748 字节 |
| Mock App Debug APK | 已生成，816411 字节 |
| Git 空白错误检查 | `git diff --check` 无错误 |

唯一 Python 警告来自 FastAPI TestClient 依赖链的 Starlette/httpx 弃用提示。Android 构建仍提示 Gradle 10 弃用兼容问题和 SDK XML v4/v3 工具版本差异。

## 五、Evaluation 可信度

本轮新增的是用户提供的脱敏、结构化淘宝页面 fixture，不是实时网页采样，也没有人工标注声明。阶段13核心指标保持原值：5 个合成树 fixture 的平均节点保留率 0.5714；8 个未人工复核 synthetic 样本的规则/混合解析准确率 1.0；10 次相同 Mock E2E 的任务和动作成功率 1.0；本机 Mock E2E 平均延迟约 7.8086ms。阶段16另记录了 2 条淘宝 fixture 商品回放，但不生成真实平台准确率或实时延迟指标。

这些结果只能证明离线 runner 和受控流程可复现，不能证明真实购物平台准确率、真实设备延迟、Agent 泛化能力或生产吞吐。

## 六、剩余阻断项

### P0——真实平台验收阻断

1. 无实时淘宝 DOM/ARIA 选择器验证，也无 Meituan/JD 的真实平台 Adapter；当前淘宝 fixture 是用户提供的结构化脱敏数据。
2. 无真实应用 Bad Case、弹窗、加载态、登录态和规格选择恢复验证。
3. Android 无物理设备或模拟器运行证据；这不阻断当前桌面端主线，但仍是移动端未完成项。

### P1——高可信质量阻断

1. CI 尚无远端执行记录；没有 coverage 门槛、lint、静态类型检查和 pre-commit。
2. Android JVM 测试数量仍少，无 instrumented/UI 测试；本轮设备桥接主要由编译和后端契约测试覆盖。
3. 设备共享令牌默认空值，仅适用于本机开发；没有设备注册、令牌轮换和多租户授权。
4. Android 尚未接入 WebSocket event client；当前 Android 桥接使用 polling，event 路径仍是后端基准实现。
5. 进程内设备会话没有持久化、背压、多实例协调和断线重投。
6. Evaluation 数据仍小且全部为 synthetic/Mock。

### P2——持续优化

1. 消除 Gradle 10 和 SDK XML 工具链警告。
2. 解决 TestClient 弃用警告并加入覆盖率、Ruff/类型检查。
3. 为桥接增加退避、抖动、命令确认租约和可观测指标。
4. 在真实设备条件下重新测量 polling/event 延迟、失败率和分位数。

## 七、最终判定

- **离线技术演示：通过。**
- **淘宝脱敏结构 fixture 只读回放：通过。**
- **真实设备开发基线：通过，但运行验证待办。**
- **实时淘宝网页和真实跨平台比价能力：不通过/未完成。**
- **生产上线：不通过。**

机器可读版本见 [project_acceptance_2026-08-09.json](../evaluation/reports/project_acceptance_2026-08-09.json)。
