# 阶段3报告——Accessibility Tree 压缩

日期：2026-08-08

## 范围

本阶段实现确定性 Observation 表示流水线，不实现 Action Grounding、Workflow、Agent 或真实平台。

## 流水线

```text
Raw Observation
  → 归一化
  → 不可见节点清理
  → 空节点清理
  → 结构节点清理
  → 保守合并重复叶节点
  → 交互节点优先级排序
  → Compact Observation + CompressionStats
```

空文本但 clickable、editable 或 scrollable 的节点会保留；不可见非交互节点可移除，但其有效子节点会提升。重复商品卡不会被粗暴合并。

## 统计字段

```text
raw_node_count
compressed_node_count
compression_ratio = compressed_node_count / raw_node_count
raw_serialized_chars
compressed_serialized_chars
processing_latency_ms
```

ratio 是保留节点比例，不是准确率或生产性能指标。

## Fixture 与验证

Fixture 覆盖正常商品列表、空节点、嵌套布局、空文本交互节点、重复商品卡和空 observation。

```text
后端：19 passed，1 warning
normal_product_list：10 → 7 nodes，retained ratio 0.7
```

所有 fixture 都是 synthetic 测试数据，未人工复核。完整原始数据见 [phase3_tree_compression.json](../evaluation/reports/phase3_tree_compression.json)。

## 完成判断

压缩实现、focused tests、CLI、synthetic fixtures、原始 benchmark 和文档均已完成。

## 下一阶段

阶段4：Action Grounding 与 Android Executor MVP。
