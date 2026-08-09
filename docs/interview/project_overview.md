# PriceSight 面试项目说明

本文只使用仓库中已经实现并在 [最终验收报告](../../evaluation/reports/project_acceptance_final.md) 中记录的证据。`fixture`、`Mock`、`BUILD_ONLY` 和真实公开页面只读 smoke 不混称。

## 30 秒介绍

PriceSight 是一个安全模式的跨平台商品比较 Computer-Use Agent 原型。它通过 Android Accessibility Tree 或浏览器 DOM/ARIA 生成结构化 Observation，先用 YAML Workflow 执行确定性步骤，再用结构化 Agent 处理商品选择和规格歧义；动作经过 `observation_id` 校验、目标 grounding 和 SafetyGuard 后才执行。平台差异收敛在 Adapter，商品归一化后按规格、数量和有效单位价比较。当前已验证后端、Mock Chromium、淘宝 fixture 和一次淘宝公开页面只读 smoke；Android Runtime、人工标注评测和生产交付仍未完成。

## 2 分钟介绍

这个项目要解决的是“让 Agent 在购物页面上可靠地观察、理解和操作”，而不是建设电商后端。任务从用户目标开始，经 Task Router 分流到 YAML Workflow 或 Agent Planner。Workflow 负责打开搜索、输入关键词、提交等稳定步骤；Planner 只处理候选商品、规格歧义和异常恢复。

当前页面被转换成紧凑 Observation。Android 端由 AccessibilityService 导出 framework-neutral DTO，浏览器端由 BrowserRuntime 从 DOM/ARIA 生成相同方向的 Observation。动作不是直接执行 LLM 的自由文本，而是先经过结构化 schema、target grounding、SafetyGuard 和当前 `observation_id` 校验。执行后重新观察并验证状态变化，旧页面动作返回 `STALE_OBSERVATION`。

商品抽取采用规则优先的 Hybrid Parser：数量、单位、规格和明确价格先 deterministic parse，语义组合和不完整描述才走结构化 LLM fallback，schema 失败则 fail closed。平台层通过 `PlatformAdapter` 转成 `NormalizedProduct`，Comparison Engine 使用 effective unit price、数量、规格和 confidence，而不是比较孤立页面数字。

安全边界是硬约束：订单确认、支付、支付密码、验证码和身份验证触发 STOP。Mock Chromium 已验证订单确认返回 `SAFETY_BLOCKED` 且没有提交订单。最终验收还完成了一次淘宝公开搜索页只读 smoke；这证明了本次公开页面读取链路，不证明登录态、真实下单或长期稳定性。

## 系统架构

```text
User Goal
  ↓
Task Router
  ├─ YAML Workflow
  └─ Structured Agent Planner
          ↓
Action Harness + SafetyGuard + observation_id
          ↓
Runtime Port
  ├─ BrowserRuntime (DOM/ARIA)
  └─ Android Accessibility + DeviceBridge polling
          ↓
Observation / compression
          ↓
PlatformAdapter
  ├─ Taobao
  ├─ JD fixture
  ├─ Meituan fixture
  └─ Mock
          ↓
Hybrid Parser → NormalizedProduct → Comparison Engine / OfferCache
```

主要实现位置：`backend/app/runtime`、`backend/app/observation`、`backend/app/action`、`backend/app/workflow`、`backend/app/agent`、`backend/app/platform`、`backend/app/parser`、`backend/app/comparison` 和 `backend/app/transport`。Android 设备侧主要在 `android-client/app/src/main`。

## 面试官可能深挖的 20 个问题及回答依据

### 1. 为什么用 Accessibility Tree，而不是只做截图 OCR？

Accessibility Tree 能提供文本、content description、resource id、clickable、editable、scrollable、bounds 和层级等动作语义，适合 target grounding 和状态验证。截图/OCR 可以作为未来补充，但当前仓库的 Android 主链路是 Accessibility DTO；不要声称已经实现 OCR。

依据：`android-client/app/src/main/java/com/pricesight/androidclient/ObservationModels.kt`、`ObservationCollector.kt`、`backend/app/observation/models.py`。

### 2. 为什么浏览器也采用 Observation，而不是让 Agent直接读 HTML？

浏览器 Runtime 与 Android 需要统一动作和观察契约。BrowserRuntime 把 DOM/ARIA 节点转换成 compact Observation，Adapter 只处理平台语义，不依赖 Runtime 内的淘宝 selector。这样 Browser Mock、淘宝页面和 Android 可以共享 Action Harness/Workflow 的验证边界。

依据：`backend/app/runtime/browser.py`、`backend/app/platform/web/adapter.py`。

### 3. Observation Tree 如何剪枝？

流程是归一化、不可见节点清理、空结构节点清理、保守去重、交互节点优先级排序和紧凑序列化。空文本但可点击、可编辑、可滚动、有 bounds 或有重要子节点的节点会保留。压缩结果可记录节点数、字符数、保留比例和延迟。

依据：`backend/app/observation/compressor.py` 与其测试。

### 4. 上下文过长怎么处理？

不把历史 UI Tree 无限累积给 Agent。当前设计使用 compact current Observation，并限制 action history、observation size、retry、LLM calls 和 workflow steps；只保留当前目标、平台、工作流状态、最近动作/结果、约束和安全状态。这个项目没有声称已经完成大规模生产上下文 benchmark。

依据：`backend/app/agent`、`backend/app/workflow`、`docs/ARCHITECTURE.md`。

### 5. 为什么必须有 observation_id？

GUI 页面可能在动作规划后已经变化。`observation_id` 把动作绑定到它所依据的页面，后端入队和下发时都核对最新观察，执行器和 Android bridge 还会再次检查；不一致就返回 `STALE_OBSERVATION`，不使用旧坐标继续操作。

依据：`backend/app/action/executor.py`、`backend/app/transport/session.py`、`backend/app/transport/store.py`、`DeviceBridgeClient.kt`。

### 6. 如何避免 Agent 基于旧页面点击？

动作按 resource id、node id、精确文本、归一化文本、fuzzy match、当前 bounds 的顺序 grounding。坐标只来自当前 Observation；动作执行前检查 observation id，重要动作后重新 observe 并验证期望状态。重复相同状态和动作会要求 replan。

依据：`backend/app/action/matcher.py`、`executor.py`、`workflow/engine.py`。

### 7. 为什么规则 + LLM，而不是所有输入都交给 LLM？

数字、数量、单位、规格和明确价格是可测试的 deterministic problem，规则更容易解释、回归和 fail closed。LLM 适合组合关系、商品标题噪声和多候选语义判断。规则先跑，只有低置信或 ambiguity 才调用 provider，减少不必要的模型依赖。

依据：`backend/app/parser/product.py`、`quantity.py`、`hybrid.py`。

### 8. LLM 输出如何保证可用？

LLM provider 返回结构化 JSON，经过 Pydantic schema validation；解析失败不会猜测执行，而是保持失败/歧义状态。FakeLLMProvider 只用于测试路由和 schema fail-closed，不代表线上模型准确率。

依据：`backend/app/llm`、`backend/app/parser/hybrid.py`、`evaluation/reports/evaluation_v2.md`。

### 9. 多件装和赠品怎么处理？

规则 parser 将容量、包装数量和容器单位分开，赠品数量保持与主购买量分离；例如 `1L×2 + 赠250ml×2` 不把赠品直接并入主商品数量。复杂组合仍可标记 ambiguity，交给结构化 fallback。

依据：`backend/app/parser/quantity.py` 和 Evaluation v2 的 `gift-water`、`buy-2-get-1` case。

### 10. 为什么不能直接比较页面显示价格？

不同平台可能显示单件价、套餐价、券后价或区间价。标准化后的比较使用 effective unit price，同时考虑 quantity、specification 和 confidence；缺少关键字段时不能把结果包装成可靠结论。

依据：`backend/app/platform/models.py`、`backend/app/comparison/engine.py`、阶段5 Adapter 报告。

### 11. Adapter 怎样支持淘宝、JD、美团？

统一 `PlatformAdapter`/`BasePlatformAdapter` 提供页面识别、商品抽取、详情抽取、标准化和 safety boundary。Taobao 有专用网页/fixture Adapter，JD 和 Meituan 已使用相同接口做 fixture 验证；Runtime、Agent 和核心 Workflow 不复制三套。当前没有声称 JD/美团 live 验证。

依据：`backend/app/platform/base.py`、`taobao/adapter.py`、`jd/adapter.py`、`meituan/adapter.py`。

### 12. BrowserRuntime 怎样实现？

`launch_browser` 启动带 allowlist 的 Playwright Chromium，`BrowserRuntime.observe()` 读取 DOM/ARIA 并生成 Observation，动作通过统一 `ActionDevice` 接口执行。离开 allowlist、遇到风险/订单状态时停止。Mock Web E2E 已实际运行；淘宝 live smoke 仅做公开页面只读。

依据：`backend/app/runtime/browser.py`、`scripts/run_browser_mock.py`、`scripts/run_taobao_readonly.py`。

### 13. Android bridge 的闭环是什么？

AccessibilityService 采集 Observation 并上传后端，后端根据最新 observation_id 排队动作；DeviceBridge polling 获取带 lease 的动作，AndroidActionExecutor 执行，再回传结果。代码中有 action_id/command_id 去重、backoff/jitter、超时和生命周期。由于没有 emulator/AVD，本仓库没有把 instrumented loop 写成 Runtime Verified。

依据：`PriceSightAccessibilityService.kt`、`DeviceBridgeClient.kt`、`AndroidActionExecutor.kt`、`backend/app/main.py`、`transport/store.py`。

### 14. 为什么动作需要 lease 和 idempotency？

设备可能断线、poll 重试或 callback 重复。SessionStore 的 lease 防止同一 action 同时发给两个 consumer，lease timeout 支持恢复，retry count 限制重试，action_id/command_id 防止重复执行，completed action 不再下发。当前实现是 InMemory + SQLite 的本地单体方案，不是分布式队列。

依据：`backend/app/transport/store.py`、`backend/tests/test_session_store.py`。

### 15. 为什么订单确认必须停止？

比较和购物决策可以在安全范围内自动化，但真实订单和支付具有不可逆外部副作用。项目要求任何订单提交、支付、密码、验证码和身份验证页面触发 `SafetyDecision.STOP`；Mock Chromium 直接回归了 `SAFETY_BLOCKED`，不会提交订单。

依据：`backend/app/core/safety.py`、`backend/app/action/executor.py`、`docs/SAFETY.md`。

### 16. Evaluation 为什么不直接说 85% 或 100% 准确率？

当前 10 条样本中 8 条 synthetic、2 条 fixture，全部 `UNREVIEWED`，没有 `HUMAN_VERIFIED`。因此 Rule 8/10、Hybrid FakeLLM 10/10 只能说明当前期望字段与机器输出的一致性，不能支撑人工真实准确率或复杂商品识别简历指标。

依据：`evaluation/datasets/evaluation_v2.jsonl`、`scripts/run_evaluation_v2.py`、最终验收 JSON。

### 17. 典型 Bad Case 是什么？

已覆盖并可单独回放：多件装、多规格、赠品、数量歧义、单位歧义和标题噪声；`taobao-iphone17-item-1/2` 是标题营销噪声导致 rule parser 需要语义 fallback 的例子。第二件优惠、券后价、价格区间、动态价格、popup/loading 等仍缺少代表性样本。

依据：`evaluation/reports/evaluation_v2.md`、`hybrid_parser_after_optimization.md`。

### 18. Mock E2E 证明了什么，不能证明什么？

它证明 Workflow、Runtime Port、Action Harness、fresh observation、价格读取和安全边界在控制性环境中可复现；它不能证明真实淘宝/JD/美团 selector、真实账号状态、网络稳定性或 Android Accessibility 运行成功。报告对 Mock、fixture 和 live smoke 分开记账。

依据：`scripts/run_browser_mock.py`、`evaluation/reports/project_acceptance_final.md`。

### 19. 当前最大的技术限制是什么？

第一是 Android runtime 没有 emulator/AVD/物理设备证据；第二是 Evaluation 没有人工标注数据；第三是 JD/美团没有 live 只读验证；第四是远端 CI 没有运行记录，Android lint 还受离线依赖缓存阻断。SQLite、真实模型和生产吞吐也没有做分布式/长期验证。

依据：最终验收报告的 P0/P1/P2 清单。

### 20. 如果继续迭代，下一步是什么？

先补可复现的 Android Emulator 环境并运行已有 instrumented test；然后采集经过脱敏和人工复核的真实 Bad Case，扩大 Evaluation；再分别做 JD/美团公开只读 smoke。所有新结果仍需按 `VERIFIED`、`FIXTURE_VERIFIED`、`MOCK_VERIFIED`、`BUILD_ONLY`、`NOT_VERIFIED`、`BLOCKED` 分类，不能用 Mock 替代真实验证。

## 可核验命令

```powershell
uv run python scripts/run_quality_gate.py
uv run python scripts/run_browser_mock.py
uv run python scripts/run_taobao_fixture_replay.py
uv run python scripts/run_evaluation_v2.py
```

最终验收结果和当前限制以 `evaluation/reports/project_acceptance_final.md/json` 为准。
