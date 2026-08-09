# 面试说明

## 为什么使用 Accessibility Tree

Accessibility Tree 提供可解释的文本、控件语义、资源 ID、可交互属性和 bounds，适合做目标定位、状态验证和安全判断。它比只依赖截图更容易复现，也不需要把所有视觉内容交给模型。

## 为什么不直接把截图给多模态模型

截图可以补充视觉信息，但不稳定地表达控件身份、可编辑状态、滚动状态和动作能力。当前项目优先使用结构化 Accessibility Observation；未来遇到纯 Canvas 或视觉缺失页面时，截图可以作为受控 fallback，而不是替代确定性安全检查。

## 为什么规则 + LLM

数量、单位、规格和价格中的稳定模式先由规则解析，结果可解释、便宜、容易测试。只有低置信度或有歧义时才调用结构化 LLM fallback，并用 Pydantic 校验返回值。FakeLLMProvider 保证没有密钥时仍可测试。

## 为什么 Workflow + Agent

打开搜索、输入关键词、返回上一页等步骤稳定且适合 YAML Workflow。商品结果选择、规格等价判断和异常恢复具有歧义，交给 Agent。这样减少不必要的模型调用，同时保持可控的重试和安全边界。

## Observation 如何压缩

流水线为：归一化 → 不可见节点清理 → 空结构节点清理 → 保守去重 → 交互节点优先级排序。空文本但 clickable、editable 或 scrollable 的节点不能直接删除。阶段13汇总的非空 synthetic fixture retained ratio 平均为 0.5714，不能解释为真实 App 通用压缩率。

## Action Grounding 如何实现

Action Harness 按 resource ID、node ID、精确文本、归一化文本、fuzzy match、当前 bounds 的顺序匹配。动作携带 `observation_id`，观察变化后旧动作会被标记为 `STALE_OBSERVATION`。执行后重新观察并按期望页面/文本/观察变化验证。

## 如何解决 stale UI

每次重要动作后获取 fresh observation；重试时重新观察并重绑定 observation ID。相同 observation hash 和 action 连续重复会触发 `REPLAN_REQUIRED`，工作流转为 `NEEDS_AGENT_DECISION`，而不是无限点击。

## 如何评测 Agent

项目使用合成 parser dataset、Mock Shopping App、Fake Device 和可复现 runner。阶段13至少汇总 tree compression ratio、parser accuracy、task/action success、retries、steps、LLM calls、E2E latency、cache hit rate 和 safety-stop accuracy，并在报告中标明数据范围。

## 如何避免无限循环

Workflow 有最大步骤数和 retry limit；Agent 有调用预算；Action Harness 有重复状态检测；安全页面直接 stop。每一种停止原因都使用显式状态，而不是吞掉异常。

## 为什么不用 LangChain

当前任务需要小而明确的 provider abstraction、结构化 Pydantic 输出、可控的重试和 Fake provider。引入完整编排框架会增加隐藏状态和依赖，不能替代项目自身的安全和动作 grounding。未来若出现确实需要的复杂 tool graph，再单独评估。

## Event-driven 为什么可能比 polling 快

Polling 要按间隔主动询问，最坏需要等待下一个轮询周期；event-driven 在 Accessibility event 到达时即可唤醒 backend，并可通过稳定化窗口合并事件。但具体结果依赖设备、网络、事件洪泛和稳定化参数。本机阶段12基准在 1 ms 模拟延迟和 1 ms 稳定化条件下，polling 平均 1.8174 ms，event 平均 29.1859 ms，说明当前 Windows fake benchmark 不能证明 event 更快，只证明两条路径可测量且基线被保留。

## Cache 如何设计

缓存 key 包含 platform、store、normalized product 和 specification。默认内存缓存便于测试；需要本地持久化时使用 SQLite。每次 lookup 记录 hit/miss、age、platform、store、product 和 specification；缓存不会绕过安全检查，也不会单独触发购买动作。

## 真实 App 和 Mock App 的差异

Mock App 的页面、节点、价格和状态变化是确定的，适合验证逻辑、回归和安全停止。真实 App 可能有登录、动态加载、弹窗、A/B UI、权限和网络延迟，因此真实 selector、成功率和延迟必须单独采集，不能把 Mock 结果冒充真实平台结果。

## 主要 Bad Cases

当前分类包括 `TARGET_MISSING`、`DUPLICATE_TARGET`、`STALE_OBSERVATION`、`PAGE_TRANSITION_DELAY`、`UNEXPECTED_DIALOG`、`SPEC_AMBIGUITY` 和 `ACTION_NO_EFFECT`。阶段13可复现的离线案例覆盖目标缺失、重复目标和重复失败重规划；真实页面转场、弹窗和规格歧义仍待真实脱敏 fixture。
