# PriceSight 面试 Bad Case

## 1. AndroidX Test Harness 干扰 AccessibilityService 生命周期

- symptom：同包 instrumented test 会停止或干扰承载 AccessibilityService 的目标包。
- root cause：测试 runner 生命周期与被测服务生命周期耦合。
- fix：使用 External Runtime Harness；由 ADB、Backend API 和 Emulator 真实状态编排，不伪造动作结果。
- evidence：阶段 9D External Harness；状态为 MOCK_RUNTIME_VERIFIED。
- lesson：测试工具的生命周期问题不能被误写成 Runtime 业务失败，也不能用 Mock 替代真实链路。

## 2. SCROLL assertion 不能依赖 node ID

- symptom：滚动后 node ID 可能保持不变，单看 ID 无法证明页面发生了可见状态变化。
- root cause：Accessibility 节点标识不是稳定的页面内容 fingerprint。
- fix：比较 visible text、bounds 和 visibility fingerprint。
- evidence：阶段 9D Harness 修复。
- lesson：状态断言应比较用户可见语义，而不是脆弱的结构标识。

## 3. Stale Observation

- symptom：页面变化后旧动作仍可能命中旧坐标。
- root cause：动作没有绑定规划时的 Observation 版本。
- fix：入队和下发双重 observation_id 校验，返回 STALE_OBSERVATION 并重新观察。
- evidence：Action/DeviceBridge regression 和 Android Harness。
- lesson：Computer-Use Agent 的动作必须带状态版本。

## 4. Price Range

- symptom：199-399 被错误地当成 199 或 399。
- root cause：展示区间没有唯一商品价格。
- fix：PriceParser fail closed，不选择端点。
- evidence：Parser regression test 和 Evaluation Bad Case。
- lesson：宁可报告信息不足，也不能生成看似精确的错误比较。

## 5. Effective Price

- symptom：券、满减、第二件优惠的展示价与最终可比价不同。
- root cause：优惠条件、购买数量或阈值可能缺失。
- fix：只支持显式券后价、无门槛券、数量明确的第二件优惠；其他情况返回 null。
- evidence：PriceParser regression tests；状态 IMPLEMENTED_WITH_REGRESSION_TESTS，HUMAN_EVALUATION_NOT_ESTABLISHED。
- lesson：有效价格应有清晰 contract 和 fail-closed 边界。

## 6. Unit Schema

- symptom：GB 被误解析为 g，mm/inch structured output 被 schema 拒绝。
- root cause：业务单位枚举不完整且正则边界不足。
- fix：补全 GB/TB/mm/cm/m/inch/sheet，保留非法单位拒绝；数字存储/长度进入 specification components。
- evidence：Parser 17 tests，schema failure 从阶段 11 人工集 3/29 降为 1/29。
- lesson：schema 完整性与 fail-closed 必须同时维护。

## 7. Evaluation Exact Match

- symptom：字段指标非零，但 exact 仍很低。
- root cause：exact 要求同一条样本的 product、quantity、specification、displayed price，以及可评估的 effective price 同时通过。
- fix：冻结 EXACT_CORE_V1 与 EXACT_STRICT_V2，分别报告字段和分母；不把两个版本直接比较。
- evidence：CORE Human 5/40、STRICT Human 2/40、HOLDOUT 两者 0/8。
- lesson：指标定义和分母比单一百分比更重要。

