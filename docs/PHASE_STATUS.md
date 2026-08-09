# 阶段状态

更新时间：2026-08-09

## 阶段 4：Android 双向闭环 Runtime 验证（BLOCKED）

- 完成 Backend action_id 去重、重复 callback 幂等、lifecycle 状态和 observation_id 双重校验保留。
- 完成 Android DeviceBridge 指数退避、jitter、timeout、bounded retry、command duplicate protection 和 lifecycle callback 字段。
- 新增 Mock App instrumented/UI test 与 Android Bridge runtime harness。
- 本机仅有 ADB，没有 Emulator、AVD 或 Android 34 system image；Emulator/system image 下载未通过当前审批通道，因此没有执行真实 Android runtime。
- 报告：[android_runtime_validation.md](../evaluation/reports/android_runtime_validation.md)。本阶段不得写成 Runtime Verified；dispatch latency、execution latency、runtime success rate 均为 `NOT_MEASURED / BLOCKED`。

## 阶段 3：强化规则 + LLM Hybrid Parser（已完成）

- Parser 明确拆分为 normalize、candidate extraction、deterministic parse、ambiguity detection、optional LLM、schema validation、confidence/reason。
- `ParseResult` 新增 `parser_source`（RULE / LLM / HYBRID）、`candidate_count`、`reason_code`、`reason`、`llm_schema_valid` 和 `llm_invocation_reason`。
- 规则优先处理数量、单位、规格、明确价格、套装和简单促销；语义标题噪声和组合关系才进入 LLM fallback。
- malformed JSON、Pydantic schema 失败和 provider 异常均 fail closed，保留规则结果并记录失败原因。
- 阶段3报告：[hybrid_parser_after_optimization.md](../evaluation/reports/hybrid_parser_after_optimization.md)。报告列出两条淘宝标题噪声失败样本，并区分规则失败与 Fake LLM 回放结果。
- 当前指标未宣称真实提升：Rule `8/10`、Hybrid FakeLLM 回放 `10/10`、LLM invocation `4/10`、schema failure `0/4`；所有样本仍为 `UNREVIEWED`。

## 阶段 2：可信 Evaluation 与 Bad Case 数据集（已完成框架建设）

- 新增 `evaluation/datasets/evaluation_v2.jsonl`，保留原有 8 条 synthetic 样本，并纳入 2 条淘宝脱敏 fixture 样本。
- 新增严格 Pydantic schema、`evaluation/ANNOTATION_GUIDE.md` 和 `evaluation/bad_case_taxonomy.json`。
- 新增 `scripts/run_evaluation_v2.py`：默认全量回放，也支持 `--sample-id` 单条重放；输出 `evaluation/reports/evaluation_v2.json` 与 `evaluation/reports/evaluation_v2.md`。
- 报告分别统计 rule / Fake LLM fallback / hybrid、quantity、spec、price、ambiguous-case，并提供 numerator / denominator。
- 新增 `backend/tests/test_evaluation_v2.py` 与机器一致性回归门禁。该门禁不是人工准确率门禁。
- 当前 10 条样本均为 `UNREVIEWED`，`HUMAN_VERIFIED=0`；旧的“50% → 85%”类历史指标不被升级为真实准确率。
- taxonomy 中尚无可靠样本的类别明确标为 `NOT_REPRESENTED`，不编造样本或覆盖率。

## 已完成阶段

### 阶段0复验——优化前可复现 Baseline

- [x] 修正机器可读验收结果中淘宝状态的过时表述。
- [x] 完成 Python compile、Backend 全量测试、Browser/淘宝定向测试、Mock Chromium E2E、淘宝 fixture replay、Android 两工程 `test assembleDebug` 和 `git diff --check`。
- [x] 生成 [baseline_before_optimization.md](../evaluation/reports/baseline_before_optimization.md)。
- [ ] 实时淘宝页面、真实 Android 设备和远端 CI 仍未验证，详见 baseline 报告中的 `NOT_VERIFIED`。

### 阶段0——环境与仓库初始化

- [x] 完成 Python 3.12.1、uv、Git、FastAPI 项目初始化和健康检查。
- [x] 完成 `.gitignore`、`.env.example`、基础 README、架构、开发和安全文档。
- [x] 阶段0报告：[PHASE_0_REPORT.md](PHASE_0_REPORT.md)。

### 阶段1——后端领域骨架

- [x] 完成配置、结构化日志、安全守卫、领域异常、Pydantic DTO、Fake LLM、Fake Device 和 Fake Transport。
- [x] 阶段1后端测试通过；报告见 [PHASE_1_REPORT.md](PHASE_1_REPORT.md)。

### 阶段2——Android Accessibility MVP

- [x] 完成 Kotlin AccessibilityService、节点 DTO、递归树导出、调试 Activity、HTTP 观察导出和 Android JVM 测试。
- [x] Android `gradle test` 与 `assembleDebug` 曾通过；报告见 [PHASE_2_REPORT.md](PHASE_2_REPORT.md)。

### 阶段3——Accessibility Tree 压缩

- [x] 完成归一化、不可见/空/结构节点清理、保守去重、交互节点优先级、统计、fixture 和 benchmark。
- [x] 原始报告：[phase3_tree_compression.json](../evaluation/reports/phase3_tree_compression.json)。
- [x] 报告：[PHASE_3_REPORT.md](PHASE_3_REPORT.md)。

### 阶段4——Action Grounding 与 Android Executor

- [x] 完成 typed action、目标匹配、fresh observation 验证、stale observation 防护、SafetyGuard 和 Android executor。
- [x] 报告：[PHASE_4_REPORT.md](PHASE_4_REPORT.md)。

### 阶段5——YAML Workflow Engine

- [x] 完成 YAML loader、步骤 schema、guards、expected-state verification、bounded retry、optional step 和安全路由。
- [x] 报告：[PHASE_5_REPORT.md](PHASE_5_REPORT.md)。

### 阶段6——LLM Provider 与结构化 Agent

- [x] 完成 OpenAI-compatible、Anthropic-compatible、Fake provider、Agent Planner 和 Agent Decision Router。
- [x] 完成 malformed output、invalid action、low confidence、provider error 和安全门测试。
- [x] 报告：[PHASE_6_REPORT.md](PHASE_6_REPORT.md)。

### 阶段7——商品数量/规格解析

- [x] 完成规则优先数量、单位、规格、促销解析和结构化 LLM fallback。
- [x] 8 个 synthetic、未人工复核样本的 rule-only/hybrid accuracy 均为 1.0。
- [x] 报告：[PHASE_7_REPORT.md](PHASE_7_REPORT.md)。

### 阶段8——Mock Shopping App 与安全模式 E2E

- [x] 完成受控 Android Mock Shopping App、Python Mock Device、搜索到购物车流程和订单确认前安全停止。
- [x] 报告记录任务成功、步骤、LLM 调用、最终价、压缩统计和 safety result。
- [x] 报告：[PHASE_8_REPORT.md](PHASE_8_REPORT.md)。

### 阶段9——离线平台适配准备

- [x] 完成通用 `PlatformAdapter`、平台无关 DTO、Mock Adapter、脱敏 fixture 和优雅失败。
- [ ] 真实平台选择、设备检查和真实 Accessibility Tree 采集因明确不连接物理设备而未执行。
- [x] 报告：[PHASE_9_REPORT.md](PHASE_9_REPORT.md)。

### 阶段10——离线多来源比较核心

- [x] 完成规格保守匹配、最终价计算、不可比较拒绝、OfferCache 和 synthetic source adapter。
- [x] synthetic 比较价格为 10.90 和 11.80，第二次比较 cache hits 为 2。
- [x] 报告：[PHASE_10_REPORT.md](PHASE_10_REPORT.md)。

### 阶段11——可靠性与 Harness 工程

- [x] 完成 trace event、重新观察、bounded retry、重复状态检测、`REPLAN_REQUIRED` 和 Bad Case 分类。
- [x] 离线回归覆盖目标缺失、重复目标、瞬态拒绝、持续失败重规划和稳定 key。
- [x] 后端测试：72 passed；报告：[PHASE_11_REPORT.md](PHASE_11_REPORT.md)。

### 阶段12——事件驱动传输、缓存与性能基准

- [x] 保留 polling，新增 `TRANSPORT_MODE=polling|event`、EventDrivenTransport 和 `/ws/transport`。
- [x] OfferCache 支持可选 SQLite，并记录 hit/miss/age/平台/店铺/商品/规格。
- [x] 10 次离线 benchmark 已记录 transport latency、cache hit rate、LLM calls/task、steps/task 和 task success rate。
- [x] 后端测试：79 passed；报告：[PHASE_12_REPORT.md](PHASE_12_REPORT.md)。

### 阶段13——Evaluation、README 与审计固化

- [x] 为 Mock E2E 增加 action attempts、action success rate 和 safety-stop correctness。
- [x] 新增最终 Evaluation runner 和 [phase13_final_evaluation.json](../evaluation/reports/phase13_final_evaluation.json)。
- [x] 完善中文版 README、架构说明、开发指南、面试指南、简历描述和最终审计。
- [x] 后端测试：79 passed；报告：[PHASE_13_REPORT.md](PHASE_13_REPORT.md)。
- [ ] 真实 App 结果和人工复核数据仍不可用，未被标记为完成。

### 阶段14——桌面浏览器 Runtime 与 Mock Web

- [x] 完成 Playwright Browser Runtime、统一 RuntimeSession 和 TaskOrchestrator。
- [x] 完成 DOM/ARIA Observation、动作执行、allowed-host 和安全停止。
- [x] 完成 Mock Web Chromium E2E；报告见 [PHASE_14_REPORT.md](PHASE_14_REPORT.md)。
- [ ] 真实购物网站 Adapter 和真实平台只读验证尚未开始。

### 阶段15——真实网页 Adapter 基础

- [x] 完成通用 `WebPlatformAdapter`、可配置 `WebSelectorConfig` 和网页证据模型。
- [x] 完成网页 fixture 采集与脱敏工具；默认不保存 Cookie、浏览器状态、截图或原始 HTML。
- [x] 完成网页商品/价格抽取、跨来源比较和证据脱敏测试。
- [x] 根据用户指定淘宝，完成 `TaobaoPlatformAdapter`、淘宝域名白名单、合成 fixture、商品列表 fixture 和用户提供的页面结构 fixture 回放测试。
- [ ] 淘宝真实网页专用选择器和只读回放仍待下一步执行；其他真实平台尚未选择。
- [x] 报告：[PHASE_15_REPORT.md](PHASE_15_REPORT.md)。

### 阶段16——淘宝页面结构只读回放

- [x] 将用户提供的淘宝页面结构 fixture 转换为统一 `Observation`。
- [x] 经淘宝 Adapter 常规网页抽取路径识别 2 条商品，识别出搜索输入、搜索提交和商品结果角色。
- [x] 生成可复现报告：[phase16_taobao_fixture_replay.json](../evaluation/reports/phase16_taobao_fixture_replay.json)。
- [x] 阶段8已访问一次淘宝公开页面并完成只读 smoke；真实登录态、长期 DOM/ARIA 稳定性、订单和支付仍未验证。
- [x] 报告：[PHASE_16_REPORT.md](PHASE_16_REPORT.md)。

### 阶段5——多平台 Adapter 架构

- [x] 新增统一 `PlatformAdapter`/`BasePlatformAdapter` 接口和 `NormalizedProduct`。
- [x] Taobao 迁移到统一 `parse_*`、标准化和安全边界兼容层，既有行为保持通过。
- [x] 新增 JD、Meituan 脱敏 fixture Adapter；未复制 Runtime、Agent 或核心 Workflow。
- [x] 比较引擎按规格、数量、有效单位价和 confidence 做推荐；加入跨平台回归测试。
- [x] 后端全量测试：122 passed，Python compileall 和 git diff --check 通过。
- [ ] 真实淘宝/JD/Meituan 页面仍未验证；fixture 结果不升级为 real platform verified。
- [x] 报告：[multi_platform_adapter_validation.md](../evaluation/reports/multi_platform_adapter_validation.md)。

### 阶段6——设备会话可靠性与轻量持久化

- [x] 建立 `SessionStore` 抽象，保留 `InMemorySessionStore` 测试实现。
- [x] 新增 SQLite 持久化实现；development 默认使用 `data/device_sessions.sqlite3`，未引入 Redis 或微服务。
- [x] 增加 action lease、lease timeout、retry count、幂等、队列上限/背压、断开设备处理和 stale action 清理。
- [x] 增加 InMemory 与 SQLite 并发测试、租约恢复、完成幂等、SQLite 重启恢复和 API 回归。
- [x] 后端全量测试：131 passed；compileall 和 git diff --check 通过。
- [ ] 未验证多进程高并发、真实 Android 断网重连和生产级故障转移。
- [x] 报告：[session_store_validation.md](../evaluation/reports/session_store_validation.md)。

### 阶段7——CI、Coverage、Lint、Typing 与最终验收

- [x] CI 拆分为 `python-quality`、`python-test`、`browser-test`、`android-test-build`。
- [x] Python 接入 Ruff、mypy、compileall、pytest/branch coverage 和轻量 pre-commit。
- [x] 当前 132 个测试的 branch coverage 为 85%，门槛设为 80%。
- [x] SafetyGuard、Parser、PlatformAdapter、TaskOrchestrator、DeviceSession 和 Action Harness 有重点回归覆盖。
- [x] Android Client/Mock App 的 unit test 与 assembleDebug 本地通过；CI 已加入 lintDebug。
- [ ] 本机离线 lint 因缺少 `lint-gradle:31.5.2` 阻断；远端 CI 尚无运行记录。
- [x] 报告：[ci_quality_validation.md](../evaluation/reports/ci_quality_validation.md)。

### 阶段1——淘宝实时网页只读链路验证

- [x] 增加淘宝页面状态识别、host allowlist、DOM/ARIA 可选证据字段和有序 selector fallback。
- [x] 增加 `scripts/run_taobao_readonly.py`，只读 runner 入口和非变更行为测试通过。
- [x] 浏览器入口实际访问淘宝公开搜索页并观察到搜索控件、商品链接和价格文本。
- [x] 阶段8重新执行公开页面只读 runner：生成实时 Observation，抽取 140 个商品链接和 45 个展示价格，无外部副作用。
- [ ] 该结果只覆盖一次公开搜索页只读 smoke，不代表登录态、长期 selector 稳定性、真实订单或支付能力。
- [x] 报告：[taobao_live_readonly_validation.md](../evaluation/reports/taobao_live_readonly_validation.md)。

## 当前能力

- Action 可基于 fresh observation grounding、执行和验证，并拒绝 stale observation。
- Workflow、Agent、解析、平台边界、Mock E2E、比较、缓存和评估均有离线实现。
- polling/event 两条传输路径均可测试，缓存支持内存和本地 SQLite。
- SAFE MODE 会在订单、支付、密码、验证码和身份验证场景停止。
- Mock Shopping App 的安全模式 E2E 可重复运行，不能代表真实平台结果。
- 后端可按设备保存最新观察、排队动作、下发动作并接收执行结果。
- Android Accessibility Service 已装配动作执行器和 polling bridge，可形成上传、轮询、执行、回传代码闭环。
- 动作入队和下发均校验 `observation_id`；过期动作不会发送给设备。
- Browser Runtime 已实现 DOM/ARIA Observation、Playwright 动作执行、域名 allowlist 和安全停止。
- 本地 Mock Web 浏览器 E2E 已通过：读取 `¥10.90`，订单确认边界返回 `SAFETY_BLOCKED`，未提交订单。
- 已具备真实网页只读接入基础：通用 Web Adapter、选择器配置和脱敏 fixture 采集工具。
- 淘宝 Adapter 已完成脱敏 fixture 回放和一次公开页面只读 smoke；结果不代表真实订单或支付流程。

## 最终评估指标

| 指标 | 实测值 | 范围 |
|---|---:|---|
| Tree compression retained ratio mean | 0.5714 | 5 个非空 synthetic fixture |
| Rule-only / Hybrid parsing accuracy | 1.0 / 1.0 | 8 个 synthetic、未人工复核 |
| Task / Action success rate | 1.0 / 1.0 | 10 次 Mock E2E |
| 平均重试/步骤/LLM 调用 | 0.0 / 13.0 / 1.0 | 10 次 Mock E2E |
| E2E 平均延迟 | 7.8086 ms | 本机 Python Mock Device |
| Warm cache hit rate | 1.0 | 第二次比较，2 个 fixture 来源 |
| Safety stop accuracy | 1.0 | 10 次安全停止场景 |

完整汇总见 [phase13_final_evaluation.json](../evaluation/reports/phase13_final_evaluation.json)。

## 2026-08-09 桌面端扩展复验

- 阶段7截点评分由 **65/100 提升至 82/100**；阶段8最终验收按同维度复算为 **84/100**。
- 离线工程原型、桌面浏览器开发基线和淘宝脱敏结构 fixture 回放：通过。
- 真实设备、真实平台和生产交付：不通过/未实现。
- 最新验证：后端 **101 passed**；淘宝结构 fixture 回放通过；新增浏览器 Runtime 测试 2 passed；Python 编译检查通过；Mock Web 浏览器 E2E 通过；Android Client 和 Mock App 的 `test assembleDebug` 均通过。
- 已增加：Browser Runtime、统一 RuntimeSession、TaskOrchestrator、本地 Mock Web、淘宝 Adapter、页面结构到 Observation 回放和浏览器 CI job。
- 阶段7截点剩余 P0 记录保留作历史；阶段8已补充一次淘宝公开只读 smoke，但 Meituan/JD live、人工 Bad Case 和 Android 运行证据仍缺失。

完整结论见 [PROJECT_ACCEPTANCE_REPORT.md](PROJECT_ACCEPTANCE_REPORT.md)。

## 已知限制

- 无物理 Android 设备和真实购物 App 运行验证。
- 淘宝仅有一次公开页面只读 selector/价格抽取证据；无真实 Meituan/JD 运行证据。
- 商品解析数据集未人工复核，不能称为人工标注准确率。
- Event transport 未接入真实 Accessibility event timing。
- 双向 bridge 仅通过契约测试和 APK 构建验证，尚无设备运行结论。
- 浏览器 Runtime 仅在本地 Mock Web 上实测，尚无真实购物网站只读结果。
- Playwright/Chromium 属于可选依赖，远端 CI 尚无执行记录。
- SQLite cache 是本地单进程方案，不是分布式缓存。
- 真实模型、网络、生产吞吐和真实平台成功率未测量。
- 网页 Adapter 目前仍是通用基础，尚未针对具体真实购物平台进行只读验证。
- 淘宝专用 Adapter 目前通过合成 fixture 和用户提供的结构化搜索 fixture 验证，不能代表真实淘宝网页运行结果。
- 淘宝页面结构 fixture 已可转换为统一 Observation 并走标准网页抽取链路；尚不代表实时网页结果。

### 阶段8——最终验收、Demo 与秋招材料整理

- [x] 按 2026-08-09 原验收报告的八个维度重新验收，未新增业务功能。
- [x] Python 质量门禁复验：132 passed、Ruff、mypy（79 source files）、compileall、pre-commit 和 85% branch coverage 均通过，门槛为 80%。
- [x] Browser Mock Chromium E2E、淘宝脱敏 fixture replay、跨平台 fixture tests 和 Evaluation v2 重新通过。
- [x] 淘宝公开页面只读 smoke 通过：真实页面 Observation、140 个商品链接、45 个展示价格、无外部副作用；结果不与 fixture/Mock 混合。
- [x] Android Client/Mock App unit test 与 assembleDebug 通过，明确将 APK 构建记录为 BUILD_ONLY。
- [ ] Android lint 因离线缺少 `com.android.tools.lint:lint-gradle:31.5.2` BLOCKED；无 emulator/AVD/system image，Android Runtime E2E NOT_VERIFIED；远端 CI 无运行记录。
- [x] 生成 [project_acceptance_final.md](../evaluation/reports/project_acceptance_final.md)、[project_acceptance_final.json](../evaluation/reports/project_acceptance_final.json) 和 [面试项目说明](interview/project_overview.md)。最终评分 84/100，项目仍非生产就绪。

## 后续外部前置条件

连接物理设备、采集脱敏真实 App fixture、单独完成安全评审后，才可开始真实平台 adapter 和真实运行验证。
