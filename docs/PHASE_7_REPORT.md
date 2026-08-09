# 阶段7报告——商品数量/规格解析与混合决策

更新时间：2026-08-08

## 范围

本阶段增加规则优先的单商品标题解析：文本归一化、数量/单位识别、购买数量与赠品分离、置信度/歧义判断，以及必要时的结构化 provider fallback。

## 已实现

- `ProductIdentity`、`ProductSpecification`、`Quantity`、`Unit`、`Promotion`、`ParseResult` 和 `LLMParseSuggestion`。
- Unicode、空白、`×`、`*`、ml/L/g/kg 和瓶/罐/袋/杯/盒等归一化。
- count-only package、L→ml、kg→g 和组合装/买赠/赠品数量处理。
- `HybridProductParser`：高置信规则结果不调用 provider，歧义或低置信结果使用严格 JSON fallback。
- synthetic JSONL dataset 和可复现 evaluation runner。

## 验证

```text
后端：57 passed，1 个 warning
样本：8 个 synthetic、未人工复核
rule-only accuracy：1.0
hybrid accuracy：1.0
LLM fallback rate：0.25
```

解析延迟是本地运行记录，不是生产性能指标；未调用 live model。

## 已知限制

品牌提取、完整商品等价、嵌套组合语义和价格比较仍保持保守，留给后续阶段。
