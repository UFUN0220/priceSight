# PriceSight Evaluation Metric Contract

版本：`v1_core_v2_strict`

本契约自阶段 13 起作为 Evaluation 的固定口径。报告可以增加展示字段，但不得改变以下字段含义、分母规则或 exact 版本。

## 字段匹配

- `product match`：expected product name 与 parser product name 进行大小写不敏感的完整字符串比较；任一方为空时只有双方同时为空才匹配。
- `quantity match`：比较 count、content amount、content unit、container unit。`L→1000ml`、`kg→1000g` 做确定性归一；不会放宽 count 或 container unit。
- `specification match`：比较 expected 与 parser 的 `package_type`。缺少明确包装证据时不猜测包装类型；components 保留在结构化输出中，但当前 exact field contract 不把自由文本 notes 当作可比标签。
- `displayed_price match`：比较 amount、currency、price kind；价格区间不选择端点。
- `effective_price match`：只在 expected effective price 非空且 replay source 包含价格证据时进入分母；比较 amount 和 currency。优惠条件不足时 parser 返回 null，不能用猜测填充。

## Ambiguity

- `ambiguous detection`：`ambiguity_type != none` 与 parser `ambiguous` 是否一致，按 ambiguity case 子集统计。
- `ambiguous case`：该 ambiguity case 上的完整 exact strict match，不等同于 detection accuracy。

## Exact Versions

### EXACT_CORE_V1

比较：

1. product
2. quantity
3. specification
4. displayed_price

只有存在对应 expected 字段时才进入字段分母；exact core 是同一样本上述核心字段全部匹配。该版本用于跨阶段长期比较。

### EXACT_STRICT_V2

在 `EXACT_CORE_V1` 基础上，额外比较满足 effective-price 分母条件的 `effective_price`。effective price 不具备可评估证据时不阻断该样本的 strict exact。

Phase 11 的 `5/40` 只能与 Phase 12 的 `EXACT_CORE_V1` 比较；Phase 12 的 `2/40` 是新增 strict 口径，不能描述为从 5/40 回归到 2/40。

## N/A 与分母

- 所有指标输出 `numerator`、`denominator` 和 `accuracy`。
- `denominator == 0` 时 `accuracy` 必须是 `NOT_AVAILABLE`，不得输出 0% 或 100%。
- synthetic、fixture、real_anonymized 只影响证据边界，不会自动成为 HUMAN_VERIFIED。
- `HUMAN_VERIFIED_ONLY` 只包含 `annotation_status == HUMAN_VERIFIED` 且 provenance audit 通过的样本。
- FakeLLM invocation/schema failure 只描述评测 harness 的 structured replay，不是线上模型准确率。

## 证据等级

- `LIVE_READONLY_VERIFIED`：真实淘宝公开网页的只读 Browser smoke。
- `MOCK_RUNTIME_VERIFIED`：Android Emulator + Mock Shopping App 外部 Harness。
- `FIXTURE_VERIFIED`：脱敏 Taobao/JD/Meituan/Mock fixture 回放。
- `HUMAN_OFFLINE_EVALUATION`：40 条人工复核的 reconstructed anonymized source 离线回放。
- `NOT_VERIFIED`：缺少足够真实环境证据。

