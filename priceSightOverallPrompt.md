# Mobile Price Agent — Codex 分阶段实施 Prompt

---

## 阶段 0：环境检查与仓库初始化

请开始 Mobile Price Agent 项目的阶段 0：本地开发环境检查与仓库初始化。

首先完整阅读根目录 `AGENTS.md`。

本阶段不要实现 Agent、Accessibility、Workflow 或真实平台逻辑。

目标：

1. 检查当前 Windows 开发环境：

   * Git
   * Python 3.12+
   * uv
   * Java/JDK 17
   * adb
   * Android SDK
   * Android Studio/Gradle 所需环境
2. 不要擅自安装系统级软件。如果缺失，明确报告缺少什么以及推荐安装方式。
3. 初始化 Git 项目结构。
4. 建立 Python backend 基础工程：

   * `pyproject.toml`
   * FastAPI
   * Pydantic v2
   * pytest
   * httpx
   * PyYAML
5. 创建根目录结构以及：

   * `.gitignore`
   * `.env.example`
   * `README.md`
   * `docs/ARCHITECTURE.md`
   * `docs/PHASE_STATUS.md`
   * `docs/SAFETY.md`
6. 创建最小 `/health` API，并为它编写测试。
7. 配置一个清晰的 Python package layout，不要把所有代码放进 `main.py`。
8. 不要添加目前没有实际用途的大型 Agent 框架。

完成后实际执行可以执行的测试。

最后给我：

* 环境检查结果；
* 创建的项目结构；
* 实际执行的测试命令及结果；
* 缺失环境；
* 阶段 0 是否满足 Definition of Done。

如果某个环境条件无法验证，明确写 UNKNOWN，不要假设成功。

---

## 阶段 1：Backend Domain Skeleton

开始阶段 1。

先阅读：

* `AGENTS.md`
* `docs/ARCHITECTURE.md`
* `docs/PHASE_STATUS.md`

检查阶段 0 当前代码，不要重新初始化项目。

本阶段只实现 Python backend 的核心领域骨架。

建立：

```text
core/
observation/
action/
workflow/
agent/
llm/
parser/
platform/
comparison/
cache/
transport/
```

主要完成：

1. application config；
2. logging 基础设施；
3. safety domain model；
4. Pydantic 基础模型；
   5.统一异常体系；
5. dependency injection 的最小方案；
6. FakeLLMProvider 接口骨架；
7. Fake Device / Fake Transport，使 backend 在没有 Android 设备时也能测试。

要求：

* 不实现真实 LLM API；
* 不实现 Android Accessibility；
* 不实现美团/JD/淘宝；
* 不引入 LangChain/LangGraph 等 Agent framework；
* 所有核心模型有类型声明；
* 确保 backend 可以完全脱离外部 API key 启动。

补充测试并运行完整 backend tests。

更新 `docs/PHASE_STATUS.md`。

最后总结新增抽象以及为什么这样划分。

---

## 阶段 2：Android Accessibility MVP

开始阶段 2：Android Accessibility Observation MVP。

先阅读项目现状和 `AGENTS.md`。

目标是在 `android-client/` 中创建一个最小 Kotlin Android 应用，通过 `AccessibilityService` 获取当前窗口 Accessibility Tree。

要求实现：

1. Android Kotlin 项目；
2. AccessibilityService；
3. 正确 Manifest 和 accessibility service 配置；
4. 用户主动开启服务的设置入口；
5. 获取 `rootInActiveWindow`；
6. 递归遍历 `AccessibilityNodeInfo`；
7. 转换为我们自己的序列化 Node DTO；
8. 输出字段尽可能包括：

```text
node_id
parent_id
class_name
text
content_description
resource_id
clickable
scrollable
editable
enabled
visible
bounds
depth
children
```

9. 不把 Android framework object 暴露到序列化边界之外；
10. 对 null root、节点失效、窗口切换等情况安全处理；
11. Debug UI 可以显示：

    * service enabled/disabled
    * current package
    * node count
    * latest observation timestamp

本阶段先使用简单 HTTP/debug export 方式把 Observation 发送到 FastAPI，不要提前实现 WebSocket。

如果设备通过 USB 连接，检查 `adb devices`，并支持：

```powershell
adb reverse tcp:8000 tcp:8000
```

如果没有 Android 设备，至少保证 Android project build 通过，并使用测试/fixture 验证序列化逻辑。

禁止实现支付、下单逻辑。

运行 backend tests 和 Android 能执行的 tests/build。

更新 `docs/PHASE_STATUS.md`。

---

## 阶段 3：Accessibility Tree Compression

开始阶段 3：Observation Representation 与 Accessibility Tree Compression。

读取阶段 2 已有 Node Schema，禁止重新设计 Android 整体架构。

在 backend 中实现：

```text
Raw Tree
→ Normalization
→ Invisible Pruning
→ Empty Node Pruning
→ Structural Pruning
→ Duplicate Semantic Merge
→ Interactive Node Prioritization
→ Compact Observation
```

关键要求：

1. 所有剪枝规则必须是 deterministic Python code；
2. clickable/editable/scrollable 等具有动作价值的节点不能因为空文本被误删；
3. 如果父节点本身没有语义，但包含有效子节点，需要正确保留或提升子节点；
4. 去掉明显无意义的纯布局节点；
5. 对重复文本/重复结构设计保守去重；
6. 每次压缩输出统计：

```text
raw_node_count
compressed_node_count
compression_ratio
raw_serialized_chars
compressed_serialized_chars
processing_latency_ms
```

7. 加入多份 Accessibility Tree fixture；
8. 测试必须覆盖：

   * 普通商品列表
   * 大量空节点
   * 嵌套布局
   * clickable 空文本节点
   * 重复商品卡片
   * 无 root/异常数据

增加一个 CLI 或 script：

```powershell
uv run python scripts/analyze_tree.py <fixture>
```

输出压缩前后统计结果。

不要为了得到漂亮的“45%”而调整逻辑。真实结果是多少就记录多少。

保存 benchmark 原始结果到 `evaluation/reports/`。

更新文档。

---

## 阶段 4：Action Grounding 与 Android Executor

开始阶段 4：Action Harness MVP。

本阶段建立 Backend Action Model → Target Matching → Android Action Executor。

支持动作：

```text
CLICK
SET_TEXT
SCROLL_FORWARD
SCROLL_BACKWARD
BACK
WAIT
STOP
```

设计 Pydantic Action Schema。

Target 可以包含：

```text
resource_id
text
content_description
node_id
bounds
semantic_hint
```

目标匹配按以下优先级实现：

```text
stable resource id
→ exact node match
→ exact text/content description
→ normalized text match
→ fuzzy candidate match
→ fresh coordinate fallback
```

要求：

1. 坐标只能来自当前 fresh observation；
2. 页面变化后旧 coordinate 不允许继续使用；
3. Android executor 对 action 进行实际执行；
4. 支持 `performAction()`；
5. 必要时支持 gesture click；
6. action 后重新读取 observation；
7. 验证页面是否发生预期变化；
8. 返回明确结果：

```text
SUCCESS
TARGET_NOT_FOUND
ACTION_REJECTED
STATE_UNCHANGED
TIMEOUT
SAFETY_BLOCKED
RETRY_EXHAUSTED
```

实现 deterministic SafetyGuard。

任何疑似：

```text
支付
付款
提交订单
确认支付
输入支付密码
```

必须被阻止。

使用 fixture 和 FakeDevice 为 matcher/verifier 编写完整测试。

此阶段不要接 LLM。

---

## 阶段 5：YAML Workflow Engine

开始阶段 5：Workflow Engine。

目标是把确定性 GUI 操作从 Agent 中分离。

设计 YAML workflow schema，例如：

```yaml
name: search_product
steps:
  - id: open_search
    action: click
    target:
      semantic_hint: search

  - id: input_keyword
    action: set_text
    value_from: task.product_keyword

  - id: submit
    action: click
    target:
      semantic_hint: search_submit
```

实现：

```text
WorkflowLoader
WorkflowDefinition
WorkflowStep
WorkflowContext
WorkflowEngine
WorkflowResult
```

支持：

* 顺序执行
* step timeout
* retry limit
* guards
* expected page/state
* optional step
* branching 的最小实现
* failure reason
* safety stop

先提供：

```text
search_product.yaml
inspect_product.yaml
add_to_cart.yaml
```

使用 FakeDevice + fixture 完成 integration tests。

不要为了 YAML 化而把复杂语义判断硬塞进 Workflow。

遇到需要语义判断的位置，应返回：

```text
NEEDS_AGENT_DECISION
```

为后续 Agent 接管留下接口。

---

## 阶段 6：LLM Provider + Structured Agent Decision

开始阶段 6：LLM 与 Agent Planner。

要求继续保持系统在没有 API key 时可通过 FakeLLMProvider 测试。

实现统一：

```python
LLMProvider
```

以及：

```text
OpenAICompatibleProvider
AnthropicCompatibleProvider
FakeLLMProvider
```

所有配置从环境变量读取。

不要硬编码 model、key、base URL。

Agent Planner 输入只允许包含：

```text
user goal
current page type
compact observation
workflow state
previous important action
known constraints
retry budget
```

不要把无限历史 Observation 塞入 prompt。

Agent 输出必须通过 Pydantic Structured Schema，例如：

```text
AgentDecision
Action
Target
confidence
requires_verification
reason_summary
```

业务代码不得依赖自由文本正则提取动作。

实现：

```text
Workflow → NEEDS_AGENT_DECISION
                  ↓
             AgentPlanner
                  ↓
          structured decision
                  ↓
           Action Grounding
```

加入：

* malformed model output tests
* invalid action tests
* unsafe action tests
* low confidence tests
* retry budget tests

本阶段只完成通用 Agent Loop，不接真实购物平台。

---

## 阶段 7：商品数量/规格解析与 Hybrid Decision

开始阶段 7：商品语义解析。

这是一个独立的重要模块，不要直接把全部商品标题交给 LLM。

实现 pipeline：

```text
Normalization
→ Rule Parser
→ Quantity Parser
→ Unit Parser
→ Specification Parser
→ Confidence
→ LLM fallback when ambiguous
```

建立规范化模型，例如：

```text
ProductIdentity
ProductSpecification
Quantity
Unit
Promotion
ParseResult
```

覆盖：

```text
农夫山泉 550ml×12瓶
可口可乐 330ml*6罐
1L×2瓶
250g*3袋
2杯装
1L×2 + 赠250ml×2
买2赠1
双人套餐
组合装
```

规则优先。

仅在：

```text
confidence < configured threshold
```

或存在明显歧义时使用 LLM。

建立 `evaluation/datasets/product_spec.jsonl` 初始数据集。

注意：

Codex 可以生成初始测试样本，但必须在 metadata 标记为 `synthetic`。不要把它描述为“人工标注数据”。

建立 evaluation runner，输出：

```text
rule_only_accuracy
hybrid_accuracy
llm_fallback_rate
average_parse_latency
```

结果保存到 reports。

不允许伪造提升比例。

---

## 阶段 8：Mock Shopping App + 完整 E2E

开始阶段 8。

在接入任何真实购物 App 前，创建独立：

```text
mock-shopping-app/
```

它是我们自己控制的测试购物应用。

至少包含：

```text
首页
搜索页
商品列表
商品详情
规格弹窗
优惠券
购物车
订单确认页
模拟支付页
```

提供多种 UI 情况：

* 普通商品
* 重复商品名
* 多规格
* 组合装
* 优惠券
* 长列表
* 动态加载
* 空文本 clickable node
* 嵌套规格

订单确认和支付页只是用于测试 SafetyGuard。

Agent 必须在提交订单或支付前 STOP。

打通完整：

```text
User Task
→ Workflow
→ Accessibility Observation
→ Compression
→ Agent Decision
→ Action Grounding
→ Android Execution
→ Verification
→ Result
```

建立 E2E tasks，例如：

```text
搜索可口可乐500ml
找到2瓶规格
领取可用优惠
加入购物车
读取最终价格
返回结果
```

至少能够重复运行测试。

记录：

```text
task_success
steps
retries
LLM calls
latency
safety result
```

这一步完成后，整个 Computer-Use Runtime 应该已经独立成立。

---

## 阶段 9：第一个真实平台 Adapter

开始阶段 9：真实平台试接入。

不要同时实现三个平台。

首先检查当前 Android 设备与已安装应用。

选择一个当前可测试的目标平台作为第一个 adapter。

只实现：

```text
识别应用
识别搜索页
搜索
读取商品列表
进入商品
读取商品名
读取规格
读取价格/优惠信息
加入购物车（仅 SAFE_MODE_ALLOW_CART=true 时）
```

禁止：

```text
提交订单
付款
验证码绕过
登录绕过
风控绕过
```

先捕获并脱敏真实 Accessibility Tree fixtures。

Platform-specific selector 和页面识别逻辑只能存在：

```text
platform/<target>/
```

generic Agent/Workflow 中禁止散落平台特定字符串。

真实 App UI 可能随版本变化，所以：

* selector 要支持多个候选；
* 找不到 selector 时 graceful failure；
* 保存必要的 sanitized fixture；
* 不把账号信息提交 Git。

完成一个真实平台闭环后停止，不要提前实现另外两个。

输出真实成功和失败案例。

---

## 阶段 10：多平台 Adapter + Price Comparison

开始阶段 10。

阶段 9 的第一个真实平台已经稳定后，再抽象并加入另外的平台 adapter。

目标支持：

```text
Meituan
JD
Taobao / instant retail
```

如果某个平台当前 Accessibility Tree 无法可靠读取，要明确记录限制，不允许通过伪数据宣称已支持。

建立统一：

```text
PlatformAdapter
ProductCandidate
NormalizedOffer
Promotion
FinalPrice
ComparisonResult
```

解决平台之间：

```text
商品名不同
规格表示不同
数量单位不同
原价/到手价不同
优惠表达不同
```

实现：

```text
User Query
  ↓
Normalized Requirement
  ↓
Platform A/B/C
  ↓
Product Matching
  ↓
Spec Matching
  ↓
Price Normalization
  ↓
Comparable Offers
  ↓
Recommendation
```

如果商品规格不能可靠判断为同一商品：

```text
comparable = false
```

禁止为了产生结果强行比较。

加入 cross-platform integration tests。

---

## 阶段 11：Reliability / Harness Engineering

开始阶段 11。

本阶段不要增加平台数量。

集中处理 Bad Cases 和执行可靠性。

分析当前日志和失败 fixture，按真实问题逐步实现：

```text
candidate degradation
route fallback
re-observation
bounded retry
page state verification
multi-event page intent
nested specification state machine
```

注意：

只有存在真实 Bad Case 时才加入复杂逻辑，不为了简历关键词制造抽象。

重点实现 Action Harness：

```text
Exact Match
→ Candidate Match
→ Semantic Match
→ Coordinate Fallback
→ Re-observe
→ Retry
→ Replan
```

加入重复状态检测：

如果：

```text
observation hash
+
action
```

连续重复且页面不变，应触发 replan，而不是死循环。

建立 Bad Case 分类：

```text
TARGET_MISSING
DUPLICATE_TARGET
STALE_OBSERVATION
PAGE_TRANSITION_DELAY
UNEXPECTED_DIALOG
SPEC_AMBIGUITY
ACTION_NO_EFFECT
```

保存回归测试。

---

## 阶段 12：事件驱动 + Cache + 性能 Benchmark

开始阶段 12：Efficiency Engineering。

目前系统应仍保留 polling transport。

不要直接删掉它。

新增 event-driven transport，优先使用适合 FastAPI 与 Android 双向通信的方案，例如 WebSocket。

设计：

```text
Accessibility Event
        ↓
debounce/stabilization
        ↓
Observation changed
        ↓
Backend
        ↓
Decision
        ↓
Action
```

保留：

```text
TRANSPORT_MODE=polling
TRANSPORT_MODE=event
```

这样才能公平 benchmark。

增加跨平台商品/规格映射 cache。

优先使用简单、可测试的本地持久化方案，不要为了技术栈强行引入 Redis。

记录：

```text
cache hit
cache miss
cache age
source platform
normalized product
specification
```

Benchmark：

```text
polling latency
event-driven latency
LLM calls/task
steps/task
cache hit rate
task success rate
```

同一组任务、同一设备、同一测试条件尽量重复运行。

原始结果写入：

```text
evaluation/reports/
```

绝对不要预设：

```text
90s → 40s
65%
3 → 1.3
```

最终是多少就记录多少。

---

## 阶段 13：Evaluation、README 与简历指标固化

开始最终阶段。

本阶段原则上不新增大功能。

目标是把项目整理成真正可以展示、解释和面试深挖的工程项目。

首先审计所有功能：

```text
implemented
partially implemented
not implemented
```

删除 README 中任何无法由代码证明的 claim。

完善 Evaluation。

最终至少统计：

```text
tree compression ratio
product parsing accuracy
hybrid parsing accuracy
task success rate
action success rate
average retries
average steps
average LLM calls
end-to-end latency
cache hit rate
safety stop accuracy
```

严格区分：

```text
Mock App Results
Real App Results
Synthetic Dataset
Human-reviewed Dataset
```

没有人工 review 的数据禁止标记为人工标注。

完善 README，包括：

```text
项目简介
架构图
Agent Loop
Workflow + Agent 设计
Observation Compression
Action Harness
Safety
环境配置
启动步骤
Mock Demo
真实平台适配
Evaluation
Benchmark
已知限制
目录结构
```

使用 Mermaid 画核心架构。

创建：

```text
docs/INTERVIEW_GUIDE.md
```

内容包括：

* 为什么使用 Accessibility Tree；
* 为什么不直接截图给多模态模型；
* 为什么规则 + LLM；
* 为什么 Workflow + Agent；
* Observation 如何压缩；
* Action Grounding 如何实现；
* 如何解决 stale UI；
* 如何评测 Agent；
* 如何避免无限循环；
* 为什么不用 LangChain；
* event-driven 为什么比 polling 快；
* cache 如何设计；
* 真实 App 和 Mock App 的差异；
* 项目的主要 Bad Cases。

最后基于**实际 benchmark 结果**生成一版四条中文简历描述。

任何没有测出来的数字，用 `[待实测]`，禁止编造。

最后运行：

```text
backend tests
Android tests/build
Mock App tests/build
evaluation runner
```

给出最终项目完成度审计报告。
