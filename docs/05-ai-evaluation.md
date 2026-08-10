# AI、Parser 与 Evaluation

## 数据构成

当前冻结数据集共 96 条：synthetic 与 fixture 用于 regression，40 条具备人工复核资格并进入 HUMAN_VERIFIED 口径。40 条人工来源均保留 provenance，固定划分为 DEV 32 / HOLDOUT 8，seed=`20260810`。HOLDOUT 不参与规则调优。

## 指标口径

当前正式报告同时保留两个 exact contract：

- `EXACT_CORE_V1`：DEV 5/32，HOLDOUT 0/8，ALL 16/96，HUMAN 5/40。
- `EXACT_STRICT_V2`：DEV 2/32，HOLDOUT 0/8，ALL 12/96，HUMAN 2/40。

字段级人工结果：quantity 26/40，specification 17/40，displayed price 10/37，effective price 0/12。FakeLLM structured replay 在人工集调用 29/40，schema failure 1/29。分母为零时报告 N/A；这些数字不等同于线上 LLM 或真实平台准确率。

## 解析策略

Pipeline 为 normalize → candidate extraction → deterministic parse → ambiguity detection → optional LLM fallback → schema validation → confidence/reason。数字、数量、单位、明确规格和明确价格优先由规则处理；语义歧义、多候选和不完整描述才进入 fallback。非法单位、无法确认的优惠条件和 schema 失败均 fail closed。

Effective price 支持有限的保守合同：明确券后价、无门槛券和明确第二件优惠可尝试解析；条件不足不臆测。当前人工 effective-price 分母为 12，正确数为 0，因此只能说明能力仍有限，不能宣称有效价格准确率。

## Bad Case

taxonomy 覆盖多件装、多规格、第二件优惠、满减、券后价、到手价、价格区间、赠品、SKU 混合文本、数量/单位歧义、标题噪声、信息缺失、重复节点、popup/loading 和动态价格。失败样本、expected/actual、parser_source、reason code 在 Evaluation 报告及 JSON 证据中保留。

## Evidence boundary

synthetic regression、fixture regression、人工复核、FakeLLM replay 和 live readonly evidence 分开统计。当前 HOLDOUT 为 0/8，泛化标记为 `LIMITED`；项目不发布“真实商品识别达到 85%”之类未经当前口径支持的简历指标。

重放命令、annotation guide、schema 和原始 JSONL 见：

- [人工标注指南](../evaluation/ANNOTATION_GUIDE.md)
- `evaluation/runner.py`
- `evaluation/datasets/`、`evaluation/fixtures/`、`evaluation/sources/`
- [冻结 Evaluation JSON](../evaluation/reports/evaluation_final_freeze.json)
