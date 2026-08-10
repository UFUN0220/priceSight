# 人工标注指南入口

这是阶段最终人工标注指南的兼容入口。完整规则请阅读：

[evaluation/ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md)

本阶段 Codex 不会新增或自动标记 `HUMAN_VERIFIED` 样本。人工填写文件为：

```text
evaluation/datasets/human_annotations.jsonl
```

当前清理重复 sample_id 后，已有 22 条 `HUMAN_VERIFIED`；要达到 40～60 条目标，还需要人工新增至少 18 条非 synthetic 样本。具体字段、null 规则、Bad Case 处理和确认条件均以 canonical guide 为准。
