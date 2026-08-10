# Documentation Consolidation

本文件记录文档体系重构本身，避免文档迁移过程变成不可审计的删除。

## 原始盘点

旧正式文档主要集中在 `docs/`：ARCHITECTURE、DEVELOPMENT、SAFETY、FINAL_AUDIT、PROJECT_ACCEPTANCE_REPORT、INTERVIEW_GUIDE、RESUME_BULLETS、PHASE_0_REPORT`～`PHASE_16_REPORT`、PHASE_STATUS。`evaluation/` 还包含 annotation guide、phase reports、acceptance reports、Evaluation reports、JSON/JSONL 数据、fixtures、sources 和 runner/scripts。

分类为：

| 类别 | 原始内容 | 唯一信息 | 处理 |
|---|---|---|---|
| 入口 | README、PHASE_STATUS | 当前能力与入口链接 | README 简化，PHASE_STATUS 改为状态页 |
| 架构 | ARCHITECTURE、DEVELOPMENT 部分 | Runtime/Observation/Agent/Adapter/Safety 设计 | ARCHITECTURE 保留，补充链接 |
| 历史 | PHASE_0～16、FINAL_AUDIT、旧 acceptance | 阶段目标、结果、失败、阻断、决策 | 合并到 03 |
| 测试质量 | DEVELOPMENT、CI report、baseline | 命令、门槛、证据等级 | 合并到 04，原始 report 保留为证据 |
| AI/Evaluation | evaluation reports、annotation docs | schema、provenance、split、bad cases、指标 | 合并到 05，JSON/JSONL/fixtures 保留 |
| 环境 | DEVELOPMENT、阶段报告 | F 盘路径、SDK/Gradle/Emulator 复现 | 合并到 06 |
| 验收 | PROJECT_ACCEPTANCE、FINAL_AUDIT、最终 freeze | 评分、证据矩阵、限制 | 统一到 07，JSON 保留 |
| 面试 | INTERVIEW_GUIDE、RESUME_BULLETS、interview/ | 叙事与 claims 边界 | 统一到 08 与 interview 子目录 |
| 原始证据 | JSON、JSONL、fixtures、scripts | 可回放数据和机器结果 | 不删除、不改成宣传文案 |

## 最终结构

```text
README.md
docs/
  README.md
  01-project-overview.md
  ARCHITECTURE.md
  03-development-history.md
  04-testing-and-quality.md
  05-ai-evaluation.md
  06-environment-and-setup.md
  07-final-acceptance.md
  08-interview-materials.md
  SAFETY.md
  PHASE_STATUS.md
  interview/
evaluation/
  ANNOTATION_GUIDE.md
  datasets/ fixtures/ sources/ reports/ runner.py
scripts/
```

## 迁移与删除原则

阶段报告的事实迁移到 03，并保留每一阶段的 evidence boundary。验收与质量口径迁移到 04/07；Evaluation 口径迁移到 05；环境信息迁移到 06；面试资料迁移到 08 和 `docs/interview/`。只有在 repo-wide 引用检查通过后，才删除重复说明文件。机器可读结果、原始脱敏输入、fixture 和生成脚本不删除。

## 质量检查

迁移后应执行：Markdown 相对链接检查、`git diff --check`、全量 backend pytest 和现有 quality gate。文档任务不改变业务代码；若历史 report 仍由 runner 生成，保留其作为 raw evidence 或更新其说明，不伪造新结果。

## 本次执行结果

- 已创建：`01-project-overview.md`、`03-development-history.md`、`04-testing-and-quality.md`、`05-ai-evaluation.md`、`06-environment-and-setup.md`、`07-final-acceptance.md`、`08-interview-materials.md`、`docs/README.md`。
- 已重写：`PHASE_STATUS.md`，改为当前冻结状态入口；已更新 `README.md`、`ARCHITECTURE.md` 和 interview overview 的正式链接。
- 已删除重复说明：`DEVELOPMENT.md`、`FINAL_AUDIT.md`、`PROJECT_ACCEPTANCE_REPORT.md`、`PHASE_0_REPORT.md`～`PHASE_16_REPORT.md`、旧 interview/resume 文档和拼写错误的 `evaluation/ANNOTATION_GUIDIDE.md`。
- 未建立 archive 副本：旧文档的独有事实已进入 03，机器可读和原始回放材料继续原位保留，避免重复拷贝造成版本分叉。
- 链接校验：`MARKDOWN_LINKS_OK`。
- 质量校验：既有 quality gate 通过，Ruff、compile、pytest 160 passed、coverage 85.69%；`git diff --check` 通过。
