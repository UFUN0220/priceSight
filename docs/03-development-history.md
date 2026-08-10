# PriceSight 开发历史与证据演进

本文是阶段报告的正式合并版。每个阶段保留目标、实现、证据、限制和后续影响；早期 synthetic/fixture/Mock 结果不与后期真实只读或人工 Evaluation 混为一谈。

## 一、基础设施与核心契约

### 1.1 Phase 0：环境与可复现 Baseline（2026-08-08）

- 建立 Python 3.12.1、uv、FastAPI/Pydantic/pytest 基线，确认仓库结构和测试入口。
- 早期环境缺少或未稳定配置 adb、Android SDK、Gradle 与物理设备；Python health/compile 和当时后端测试通过。
- 该阶段只建立证据基线，不把构建成功写成运行时验证。

### 1.2 Phase 1：Backend contracts

- 建立 Observation、Action、Runtime Port、Device Session、Fake LLM 和 API contracts。
- 12 tests passed；验证层级为 VERIFIED（单元/契约），没有真实设备证据。

### 1.3 Phase 2：Android Accessibility MVP

- Kotlin Accessibility Service、API 34、Gradle 9.7、JDK 17 兼容路径和 action contract 落地。
- Backend 13、Android JVM tests 与 assemble 通过；当时没有物理设备，故为 BUILD_ONLY/NOT_VERIFIED。

### 1.4 Phase 3：Observation compression

- 完成不可见节点、空节点、冗余结构和重复语义节点处理，并保留可点击、可编辑、可滚动节点。
- 早期普通 fixture 从 10 节点压缩到 7 节点；后续 5 个 synthetic fixture 的平均压缩比为 0.5714。这是压缩实验，不是线上性能指标。

## 二、Workflow、Agent 与 Action

### 2.1 Phase 4：Action grounding/executor

- 资源 ID、精确文本/描述、语义匹配、模糊候选和新鲜坐标 fallback 形成 action harness。
- 29 tests passed，增加 stale observation 约束和结果分类；不执行真实购买。

### 2.2 Phase 5：YAML Workflow 与 SafetyGuard

- YAML 驱动稳定步骤，Agent 只处理不确定选择；安全检测覆盖订单、支付、密码、验证码和身份验证边界。
- 39 tests passed；触发安全边界时返回 `SafetyDecision.STOP`。

### 2.3 Phase 6：Provider-neutral LLM 与 Agent

- OpenAI-compatible、Anthropic-compatible 和 Fake provider 通过统一接口接入，输出由 Pydantic schema 校验。
- 50 tests passed；未进行线上 provider accuracy 验证。

### 2.4 Phase 7：规则与 Hybrid Parser

- 建立 normalize → deterministic parse → ambiguity detection → optional LLM → schema validation pipeline。
- 57 tests passed；早期 8 条 synthetic parser 实验中的 1.0 等数值仅属于该数据集，不能写成真实准确率。

### 2.5 Phase 8：Mock Shopping App 与 E2E

- Mock App 覆盖搜索、商品详情、规格、滚动、返回和确认边界；Browser/Android action harness 具有 fresh observation 与安全停止。
- 当期 E2E 记录过 13 steps、0 retries、1 LLM、final price 10.90，以及 raw/compressed 194/166；这些是 Mock 场景证据。

## 三、比较、可靠性与 Browser Runtime

### 3.1 Phase 9：Platform Adapter

- 统一 PlatformAdapter、Taobao/JD/Meituan fixture adapter 和 NormalizedProduct；未知平台 fail closed。
- 当期 64 tests passed，Mock 识别 3 products，detail price 12.90；没有真实平台运行证据。

### 3.2 Phase 10：Comparison Engine

- 比较基于 effective unit price、quantity、specification、confidence；不直接比较页面上的单个数字。
- 当期 68 tests passed，Mock prices 10.90/11.80，store A 被推荐；不相容规格被标为不可比。

### 3.3 Phase 11：Action reliability

- 增加 trace、repetition detector 和 Bad Case：TARGET_MISSING、DUPLICATE_TARGET、STALE_OBSERVATION、PAGE_TRANSITION_DELAY、UNEXPECTED_DIALOG、SPEC_AMBIGUITY、ACTION_NO_EFFECT。
- 当期 72 tests passed；重试有边界，动作后重新观察。

### 3.4 Phase 12：Transport/cache benchmark

- 保留 polling baseline，同时加入 event transport 和 cache；早期 Windows fake benchmark 记录 polling 1.8174 ms、event 29.1859 ms、warm hit 1.0。
- 这些是小样本/模拟基准，不是生产网络性能。

### 3.5 Phase 14：BrowserRuntime 与 Mock Web

- BrowserRuntime、DOM observation、Mock Chromium E2E 和浏览器安全配置隔离完成。
- 当期 Backend 91、Browser 2；Mock price 10.90，进入安全边界后 `SAFETY_BLOCKED`，无真实站点证据。

### 3.6 Phase 15：Web Adapter 与 Phase 16：淘宝 fixture replay

- selector 配置、证据脱敏/捕获和 WebPlatformAdapter 完成；淘宝结构化 fixture replay 后端总测试达到 101。
- fixture replay 记录 2 products、prices 5999/5999，`real_page=false`；不能描述为实时淘宝。

## 四、真实只读、Android 闭环与 Evaluation 收口

### 4.1 淘宝公开页面只读链路

- 在既有 BrowserRuntime 入口上增加页面识别、selector fallback、只读 runner 和验证报告。
- 最终冻结证据为公开页面访问成功、发现 140 个 product links、45 个 displayed prices，无登录、下单或支付副作用；级别为 `LIVE_READONLY_VERIFIED`，不是完整业务任务成功。

### 4.2 Android Runtime 阶段 9B/9C/9D

- 解决 Emulator + Mock Shopping App 环境阻断，保留 AccessibilityService、DeviceBridge、observation_id 双校验、action lifecycle、SessionStore 和 SafetyGuard。
- External Harness 实际记录 18 observations、18 actions、0 failed、0 timeout；覆盖 CLICK、SET_TEXT、SCROLL_FORWARD、BACK、TARGET_NOT_FOUND、STALE_OBSERVATION、STOP、SAFETY_BLOCKED，并验证重复 action contract。
- 最终证据为 `MOCK_RUNTIME_VERIFIED`。真实淘宝/JD/美团 Android App 仍为 `NOT_VERIFIED`。

### 4.3 Evaluation provenance 与人工数据

- 经过 annotation schema、provenance audit、人工确认和固定 DEV/HOLDOUT 后，冻结数据 96 条，人工复核资格 40 条，seed `20260810`，DEV 32/HOLDOUT 8。
- 人工数据来自已有合法脱敏来源的重建/确认记录，原始 JSONL 留在 `evaluation/sources/`；synthetic、fixture、HUMAN_VERIFIED、FakeLLM 和 live readonly 证据分开计算。
- 过去的“50%→85%”类旧指标已降级为历史口径或不再作为正式结论。

### 4.4 Phase 11/12/13：Human Evaluation、schema 与最终冻结

- Phase 11 按人工 bad case 调整 Hybrid Parser；Phase 12 补充 GB/TB/mm/cm/m/inch/sheet 等业务单位，并实现保守 effective price contract；非法单位和条件不足继续 fail closed。
- Phase 12 HOLDOUT 为 0/8，说明泛化有限；Phase 13 对 exact metric contract、denominator、split seed、provenance 和最终验收评分统一口径。
- 最终冻结：`EXACT_CORE_V1` DEV 5/32、HOLDOUT 0/8、ALL 16/96、Human 5/40；`EXACT_STRICT_V2` DEV 2/32、HOLDOUT 0/8、ALL 12/96、Human 2/40。quantity 26/40、specification 17/40、displayed price 10/37、effective price 0/12。总体泛化为 `LIMITED`。
- 项目最终评估保留原八维度和权重，得分 87/100（加权 86.85）；该分数基于证据矩阵，不通过修改评分标准获得。

## 五、跨阶段不合并的指标

| 指标类型 | 可说明什么 | 不可说明什么 |
|---|---|---|
| synthetic parser | 规则逻辑回归 | 真实商品准确率 |
| fixture replay | 固定脱敏输入可重放 | 实时平台稳定性 |
| Mock Chromium/Mock App | Runtime contract 闭环 | 真实 App/生产性能 |
| live readonly | 公开网页只读访问 | 登录后完整购物任务 |
| FakeLLM replay | schema/fallback 流程 | 线上模型效果 |
| HUMAN_VERIFIED | 已人工复核样本上的字段/contract 指标 | 全平台普遍泛化 |

## 六、当前未解决项

- HOLDOUT exact 0/8，说明 parser 对未见复杂表达的泛化仍有限。
- effective price 人工正确数 0/12，促销语义仍需更多真实、可审计标注后再评估。
- 真实购物 App、真实订单、支付、验证码和生产级延迟未验证。
- 旧阶段报告中的历史文档仍需通过本次清理归档/删除，raw JSON/JSONL/fixture/script 不删除。
