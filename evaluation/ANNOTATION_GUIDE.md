# Evaluation v2 人工标注指南

## 目的

Evaluation v2 用于建立可追溯的商品解析评测集。`synthetic` 是历史规则样本，`fixture` 是仓库内脱敏页面回放，`real_anonymized` 只能在真实页面经过脱敏和人工复核后使用。三类来源都必须保留来源证据；来源类型不等于人工标注状态。

当前数据集中的样本均为 `UNREVIEWED`。在没有人工逐条复核前，不得改为 `HUMAN_REVIEWED` 或 `HUMAN_VERIFIED`，也不得将 runner 输出当成真实准确率。

## 标注流程

1. 只在本地打开样本引用的脱敏 fixture 或原始观察，不访问真实账号和付款流程。
2. 确认 `query`、商品核心名称、主购买数量、SKU/组合规格和价格口径。
3. 将营销词、赠品、第二件优惠、券后价等记录在 `ambiguity_type` 与 `expected_*` 的说明中。
4. 逐条填写 `expected_quantity`、`expected_spec`、`expected_price`、`expected_product_name`。
5. 若信息缺失，不猜测；使用 `null`，并记录 `missing_information` 或对应失败原因。
6. 复核人完成后才可设置 `annotation_status: HUMAN_REVIEWED`；第二名复核人确认一致后才可设置 `HUMAN_VERIFIED`。

## 字段约定

| 字段 | 规则 |
| --- | --- |
| `sample_id` | 永久稳定，不因 parser 修改而变化。 |
| `source_type` | 只能是 `synthetic`、`fixture`、`real_anonymized`。fixture 必须保留仓库相对路径。 |
| `raw_observation` / `fixture_reference` | 至少一个可回放来源；fixture 引用可使用 `文件#JSON路径`。 |
| `expected_quantity` | 只填写主购买数量；赠品和促销数量不得合并。 |
| `expected_spec` | 记录组合或 SKU 规格；无法从观察确认时保持空值并写明原因。 |
| `expected_price.price_kind` | 例如 `displayed`、`coupon`、`after_sale`；不同口径不能混比。 |
| `annotation_status` | 机器 runner 不得写入 `HUMAN_*`。 |
| `parser_output`、`model_output`、`final_output` | 运行产物，不是人工标签；应由报告保存，数据集初始值保持 `null`。 |

## 失败与 Bad Case

`failure_reason` 要描述可重现的原因，例如 `title_noise_not_normalized`、`price_kind_missing`、`fixture_field_absent`，不要写“模型不好”。Bad Case 分类见 `evaluation/bad_case_taxonomy.json`。每个已有 `sample_id` 都可用 runner 单独重放；空列表表示当前没有可靠样本，不能伪造覆盖率。

## 质量门槛

只有 `HUMAN_VERIFIED` 样本可以进入“人工真实准确率”分母。`UNREVIEWED`、`MACHINE_DRAFT` 和仅有 fixture 的样本可以用于解析器回归，但报告必须明确标记为机器一致性或 fixture 验证，不得用于简历级准确率声明。
