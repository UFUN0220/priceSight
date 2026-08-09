# 中文简历描述——基于阶段13实际报告

以下数字均来自 [phase13_final_evaluation.json](../evaluation/reports/phase13_final_evaluation.json) 或其引用的实际离线报告，并明确限定为 synthetic/Mock 结果：

1. 设计并实现安全模式移动端 Computer-Use Agent，采用 Accessibility Tree 压缩、YAML Workflow + 结构化 Agent、Action Grounding 与确定性 SafetyGuard，Mock E2E 在 10 次离线运行中任务成功率和安全停止准确率均为 1.0。
2. 构建保留交互语义的 Accessibility Observation 压缩流水线，5 个非空 synthetic fixture 的 retained node ratio 平均为 0.5714，并保留 clickable、editable、scrollable 空文本节点。
3. 实现规则优先的商品数量/规格解析与 FakeLLM fallback；8 个未人工复核的 synthetic 样本上 rule-only 与 hybrid accuracy 均为 1.0，未将其描述为生产或人工标注准确率。
4. 实现 polling/event 双传输基线、WebSocket 事件入口和可选 SQLite OfferCache；10 次 Mock E2E 平均 13 步、1 次 LLM 调用、7.8086 ms 本地端到端耗时，比较缓存 warm hit rate 为 1.0。
