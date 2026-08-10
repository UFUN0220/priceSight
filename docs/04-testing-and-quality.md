# 测试与工程质量

## 当前基线

本项目当前最终冻结以 commit `7b201fec3def68de0a4be5eba1c63de8f35f7d9c` 的远端 run `31413048761` 为准：Backend 172 passed，branch coverage 85%，coverage fail-under 80。Ruff、mypy、Python compile、pre-commit、Browser Mock、Android client 和 Mock Shopping App 均通过。历史 160 passed / 85.69% 属于上一轮验收口径，保留在 raw acceptance reports 中，不与当前结果混写。

## 可复现入口

在仓库根目录执行：

```powershell
uv run pytest
uv run ruff check backend
uv run mypy backend/app
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
