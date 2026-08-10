# Evaluation v2 最终人工标注指南

## 目的

Evaluation v2 用于建立可追溯的商品解析评测集。`synthetic` 是历史规则样本，`fixture` 是仓库内脱敏页面回放，`real_anonymized` 只能在真实页面经过脱敏和人工复核后使用。三类来源都必须保留来源证据；来源类型不等于人工标注状态。

当前 annotation 文件共有 86 条：40 条已声明 `HUMAN_VERIFIED`、46 条 `UNREVIEWED` synthetic。40 条目前均通过 provenance/hash 审计，但 source 是从已有 annotation raw_text 重建的脱敏文本，不是原始网页 capture。Codex、parser、FakeLLM 和 runner 都不得替人工修改状态。

## 标注流程

1. 只在本地打开样本引用的脱敏 fixture 或原始观察，不访问真实账号和付款流程。
2. 确认 `query`、商品核心名称、主购买数量、SKU/组合规格和价格口径。
3. 将营销词、赠品、第二件优惠、券后价等记录在 `ambiguity_type` 与 `expected_*` 的说明中。
4. 逐条填写 `expected_quantity`、`expected_spec`、`expected_price`、`expected_product_name`。
5. 若信息缺失，不猜测；使用 `null`，并记录 `missing_information` 或对应失败原因。
6. 复核人完成后，若仍有分歧使用 `DISPUTED`；只有人工明确确认并完成复核后才可设置 `HUMAN_VERIFIED`。

## 字段约定

| 字段 | 规则 |
| --- | --- |
| `sample_id` | 永久稳定，不因 parser 修改而变化。 |
| `source_type` | 只能是 `synthetic`、`fixture`、`real_anonymized`。fixture 必须保留仓库相对路径。 |
| `raw_observation` / `fixture_reference` | 至少一个可回放来源；fixture 引用可使用 `文件#JSON路径`。 |
| `expected_quantity` | 只填写主购买数量；赠品和促销数量不得合并。 |
| `expected_spec` | 记录组合或 SKU 规格；无法从观察确认时保持空值并写明原因。 |
| `expected_price.price_kind` | 例如 `displayed`、`coupon`、`after_sale`；不同口径不能混比。 |
| `annotation_status` | 工作文件只使用 `UNREVIEWED`、`HUMAN_VERIFIED`、`DISPUTED`；机器 runner 不得写入人工状态。 |
| `parser_output`、`model_output`、`final_output` | 运行产物，不是人工标签；应由报告保存，数据集初始值保持 `null`。 |

## 失败与 Bad Case

`failure_reason` 要描述可重现的原因，例如 `title_noise_not_normalized`、`price_kind_missing`、`fixture_field_absent`，不要写“模型不好”。Bad Case 分类见 `evaluation/bad_case_taxonomy.json`。每个已有 `sample_id` 都可用 runner 单独重放；空列表表示当前没有可靠样本，不能伪造覆盖率。

## 质量门槛

只有 `HUMAN_VERIFIED` 样本可以进入“人工真实准确率”分母。`UNREVIEWED`、`MACHINE_DRAFT` 和仅有 fixture 的样本可以用于解析器回归，但报告必须明确标记为机器一致性或 fixture 验证，不得用于简历级准确率声明。

## 本阶段人工填写入口

人工实际填写文件：

```text
evaluation/datasets/human_annotations.jsonl
```

字段模板和允许值见：

```text
evaluation/datasets/human_annotations.template.json
```

当前文件已经包含 40 条人工确认记录和 46 条 synthetic 回归记录。不要把 synthetic 行改成 HUMAN_VERIFIED；新增真实脱敏页面或经人工确认的 fixture 时，在同一个 JSONL 文件追加新 sample_id，不要重复使用既有 ID。目标总量为 40～60 条 HUMAN_VERIFIED，当前数量已达到最低门槛。

使用人工 overlay 重放：

```powershell
uv run python scripts/run_evaluation_v2.py `
  --annotations evaluation/datasets/human_annotations.jsonl `
  --json-report evaluation/reports/evaluation_human_verified.json `
  --markdown-report evaluation/reports/evaluation_human_verified.md
```

runner 会按 `sample_id` 合并 overlay。空白的 `UNREVIEWED` 队列行不会覆盖现有机器回归 expected；填写后可重放。`DISPUTED` 会保留在 ALL 中，但排除 HUMAN_VERIFIED_ONLY。runner 永远不会把 `UNREVIEWED` 或 `DISPUTED` 自动升级为 `HUMAN_VERIFIED`。

## 每条数据需要填写的字段

| 字段 | 人工填写规则 |
| --- | --- |
| `sample_id` | 来源中的稳定 ID；不得按 parser 版本改名。 |
| `platform` | `taobao`、`jd`、`meituan`、`generic` 或仓库已有平台名。 |
| `source_type` | `synthetic`、`fixture`、`real_anonymized`；合成数据永远保持 `synthetic`。 |
| `anonymized_source` | 脱敏文件路径、fixture JSON selector 或采集记录编号；fixture/real_anonymized 必须在标记 HUMAN_VERIFIED 前提交可读取的仓库内来源文件；不得放账号、Cookie、支付信息。 |
| `query` | 当时的用户查询，不自行改写成商品标题。 |
| `product_title` | 页面可见的商品标题；没有标题时留空。 |
| `raw_text` | 可复现的脱敏文本，保留影响判断的促销、SKU、数量和价格。 |
| `expected_quantity` | 只写主购买数量和主包装含量；赠品、第二件优惠数量分开写在 notes。无法确定时为 `null`。 |
| `expected_spec` | 写容量、颜色、版本、存储、套餐/组合等规格。观察不到时为 `null`，并说明原因。 |
| `expected_displayed_price` | 页面直接展示的价格口径，`price_kind` 使用 `displayed`。价格区间不能硬选一个数。 |
| `expected_effective_price` | 根据明确优惠条件可计算的实际口径；无足够条件时为 `null`，不能把 displayed price 复制过来冒充到手价。 |
| `expected_product_name` | 去除营销词后的核心商品名；无法确认时为 `null`，不要猜。 |
| `ambiguity_type` | 从 `evaluation/bad_case_taxonomy.json` 选择最主要的一个类型；必要的次要歧义写入 notes。 |
| `annotation_status` | 新行使用 `UNREVIEWED`；有明确分歧使用 `DISPUTED`；只有人工完成复核和确认后才使用 `HUMAN_VERIFIED`。 |
| `annotator_notes` | 记录判断依据、缺失字段、优惠条件和复核意见；HUMAN_VERIFIED 必须非空。 |

### 哪些字段允许 null

- `product_title`：允许空字符串，例如页面没有稳定标题。
- `expected_quantity`、`expected_spec`、`expected_displayed_price`、`expected_effective_price`：允许 `null`；必须在 `annotator_notes` 说明信息为何不足。
- `expected_product_name`：`HUMAN_VERIFIED` 当前由 schema 要求非空；无法确认时只能保持 `UNREVIEWED` 或 `DISPUTED`。
- `query`、`raw_text`、`anonymized_source`：不能为空，必须能追溯并回放来源。

`raw_text` 可以作为脱敏文本回放输入，但不能替代来源文件证据。runner 会单独审计
`anonymized_source` 是否解析到仓库内文件；路径不存在时，人工标签仍会保留，但该样本不能被报告描述为仓库内 fixture 或真实页面证据。

## 字段判定细则

### quantity

只标用户购买的主商品数量。例如 `550ml×12` 的 `count=12`、`content_amount=550`、`content_unit=ml`；`买2赠1` 的“买 2”是促销条件，不要在无法确定包装数量时标成 `count=3`；`1L×2 + 赠250ml×2` 的主数量是 2，赠品写入 notes。

### specification

规格包含容量、重量、颜色、尺寸、存储、版本、SKU 或套餐关系。不同规格没有选择依据时，`expected_spec` 可以为 `null`，`ambiguity_type` 标为 `multi_spec` 或 `sku_mixed_text`，在 notes 写清缺失信息。不要把营销词当成规格。

### displayed price 与 effective price

`expected_displayed_price` 是页面直接读到的金额，例如 `¥19.90`。`expected_effective_price` 只有在优惠条件明确且计算口径可复现时才填写，例如明确“券后 ¥17.90”。“到手价”“预估价”“第二件折扣”如果缺少门槛、会员、数量或时间条件，effective price 应为 `null`，并标记对应 Bad Case。当前 Parser 输出主要验证 displayed price；报告不会把 effective price 标注伪装成已实现的模型能力。

### 区间价格

如 `¥9.90-19.90`、`9.9 起` 或不同 SKU 的价格区间，不要选择最低价或最高价作为单值。`expected_displayed_price` 设为 `null`，`ambiguity_type=price_range`，notes 保存原始区间和无法选择单 SKU 的原因。

### 信息不足、重复节点和 popup/loading

缺失价格、规格或商品名时保留 `null`，标 `missing_information`。同一商品重复出现时在 notes 记录重复节点证据，标 `duplicate_node`，不要把重复节点当成两个商品。弹窗或加载状态遮挡主体内容时标 `popup_loading`；如果页面当时没有可确认商品信息，expected 字段保持 `null`。

### 动态价格

价格随时间、用户身份、库存或交互变化时，必须记录观察时间/条件和页面原文；无法在脱敏 fixture 中重现的，`expected_effective_price=null`，标 `dynamic_price`，不得用另一次访问的价格替代。

## 什么时候可以标 HUMAN_VERIFIED

同时满足以下条件才可以人工填写 `HUMAN_VERIFIED`：

1. 人工实际查看了脱敏原文或 fixture，不是根据 parser 输出反推 expected。
2. `source_type` 不是 `synthetic`；synthetic 只能保留为 synthetic regression。
3. quantity、spec、displayed/effective price 和 product name 已逐字段填写；无法确认的字段明确填 `null` 并解释原因。
4. `ambiguity_type` 与原文一致，优惠门槛和区间价格没有被简化掉。
5. `annotator_notes` 写明依据，并完成第二次复核或明确确认。
6. 标注人手工将状态改为 `HUMAN_VERIFIED` 后，再运行 runner；Codex、parser、FakeLLM 和 runner 都不得替你改变这个状态。

此外，`anonymized_source` 必须指向可读取的脱敏文件或仓库内 fixture。来源文件缺失不应被 runner 自动补齐；应先补文件并重新人工确认来源。

如果两名标注人无法达成一致，使用 `DISPUTED`，保留分歧说明；该样本可以进入 ALL 回归，但不会进入 HUMAN_VERIFIED_ONLY。

## 当前优先补充的 Bad Case

当前 HUMAN_VERIFIED 已覆盖：`bulk`、`unit_ambiguity`、`gift`、`quantity_ambiguity`、`sku_mixed_text`、`price_range`、`coupon_price`、`second_item_discount`、`dynamic_price`、`title_noise`、`duplicate_node`、`popup_loading`。新增记录的 `annotator_notes` 中还注明了 multi_pack、multi_spec、after_sale_price，但其正式 `ambiguity_type` 仍使用现有 taxonomy 类型；后续如需单独统计，应由人工确认后调整标签。不要为了填满列表而编造商品、价格或人工结论。
