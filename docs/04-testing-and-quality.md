# 测试与工程质量

## 当前基线

本项目最终冻结基线以 `2026-08-10` 的证据为准：Backend 160 passed，branch coverage 85.69%，coverage fail-under 80。Ruff、mypy、Python compile、pre-commit 和 `git diff --check` 均已通过。Android unit/build 与 Mock App build 采用冻结报告中的结果；External Harness 已提供 Emulator + Mock App 运行证据。

## 可复现入口

在仓库根目录执行：

```powershell
uv run pytest
uv run ruff check backend
uv run mypy backend/app backend/tests
uv run python -m compileall backend/app backend/tests
uv run coverage run --branch -m pytest backend/tests
uv run coverage report --fail-under=80
git diff --check
```

Evaluation 入口和数据口径见 [AI 与 Evaluation](05-ai-evaluation.md)。Android 命令、SDK 与 Emulator 说明见 [环境与复现](06-environment-and-setup.md)。

## 验证层级

| 能力 | 证据级别 | 说明 |
|---|---|---|
| Backend contract/parser/workflow/session | VERIFIED | 自动化测试覆盖 |
| Browser Mock Chromium | MOCK_RUNTIME_VERIFIED | Mock 浏览器运行时闭环 |
| 淘宝脱敏 fixture replay | FIXTURE_VERIFIED | 保存的脱敏结构，不是实时数据 |
| 淘宝公开页面只读 smoke | LIVE_READONLY_VERIFIED | 只读访问证据，不包含登录、下单或支付 |
| Android Emulator + Mock App | MOCK_RUNTIME_VERIFIED | External Harness 闭环 |
| Android 真实购物 App | NOT_VERIFIED | 未执行，不得外推 |
| 生产性能 | NOT_VERIFIED | 历史微基准不是生产性能 |

## 历史质量数据的使用规则

早期阶段的测试数量、压缩比、步骤数、延迟和 parser 指标保留在开发历史中，作为当时的实验记录。它们不能与最终固定 Evaluation 的字段级 exact 指标直接合并，也不能替代当前冻结基线。
