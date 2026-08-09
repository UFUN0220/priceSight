# 开发指南

## 环境与后端测试

```powershell
uv sync
uv run pytest
uv run uvicorn app.main:app --app-dir backend --reload
```

测试发现规则位于 `pyproject.toml`，测试目录为 `backend/tests`。

## Accessibility Tree 分析

```powershell
uv run python scripts/analyze_tree.py backend/tests/fixtures/observations/normal_product_list.json
uv run python scripts/benchmark_tree_compression.py
```

原始报告写入 `evaluation/reports/phase3_tree_compression.json`。

## Action Harness 与 Workflow

```powershell
uv run pytest backend/tests/test_action_executor.py backend/tests/test_workflow_loader.py backend/tests/test_workflow_engine.py
```

Action Harness 使用 fresh observation、确定性 matcher、安全门、验证器和 bounded retry。Workflow 支持 guards、期望状态、optional step、路由和 Agent handoff。

## Agent 与商品解析

```powershell
uv run pytest backend/tests/test_agent_planner.py backend/tests/test_llm_providers.py
uv run pytest backend/tests/test_product_parser.py
uv run python scripts/evaluate_product_parsing.py
```

默认使用 `FakeLLMProvider`。真实 provider 必须通过环境变量配置，不能写入 key。商品解析数据集是 synthetic、未人工复核。

## Mock E2E 与平台边界

```powershell
uv run pytest backend/tests/test_mock_e2e.py backend/tests/test_mock_adapter.py
uv run python scripts/run_mock_e2e.py
uv run python scripts/run_mock_adapter_check.py
```

Mock E2E 使用确定性 Python device；Mock APK 只做构建/测试验证，不连接真实设备。

## 阶段12传输、缓存与基准

```powershell
uv run pytest backend/tests/test_phase12.py
uv run python scripts/run_phase12_benchmark.py
```

`TRANSPORT_MODE=polling` 是默认基线；`TRANSPORT_MODE=event` 选择事件传输，事件也可通过 `/ws/transport` 发送。`OfferCache` 默认内存模式，传入 SQLite path 后启用本地持久化。基准保存原始样本，不把 synthetic 结果转换为生产性能结论。

## 阶段13最终评估

```powershell
uv run python scripts/run_mock_e2e.py
uv run python scripts/run_phase12_benchmark.py
uv run python scripts/run_final_evaluation.py
```

最终 runner 从实际报告读取指标，并区分 synthetic parser、Mock App、fake transport/cache 和未实测真实 App。详见 [FINAL_AUDIT.md](FINAL_AUDIT.md)。

## 项目级验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q backend\app scripts
```

Android client 和 Mock App 分别执行：

```powershell
F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0\bin\gradle.bat test --offline --no-daemon --console=plain
F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0\bin\gradle.bat assembleDebug --offline --no-daemon --console=plain
```

2026-08-09 的项目级验收结果和 P0/P1/P2 整改清单见 [PROJECT_ACCEPTANCE_REPORT.md](PROJECT_ACCEPTANCE_REPORT.md)。`lintDebug --offline` 因本机未缓存 `lint-gradle:31.5.2` 而未完成，不能视为 lint 通过。

## Android 构建

```powershell
F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0\bin\gradle.bat test --offline --no-daemon --console=plain
F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0\bin\gradle.bat assembleDebug --offline --no-daemon --console=plain
```

Android 和 Mock App 构建可能出现 Gradle 弃用、SDK XML 兼容和 Android API 弃用警告。没有物理设备时不得声称完成 runtime 验证。

## 环境策略

不要自动安装系统级软件。缺少工具时记录准确的 `MISSING` 或 `UNKNOWN`，并通过批准的 Windows/Android 开发渠道处理。

## 增量开发规则

每个阶段都必须保留健康检查、增加 focused tests、运行相关验证、更新 `docs/PHASE_STATUS.md`，并且不能把未来功能仅写在 README 中冒充已实现。
