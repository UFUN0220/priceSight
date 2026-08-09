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

### Evaluation v2 与 Bad Case 回放

阶段 2 的统一数据集、schema、人工标注指南和 Bad Case taxonomy 位于 `evaluation/`。一条命令重放全部样本并生成 JSON + Markdown 报告：

```powershell
uv run python scripts/run_evaluation_v2.py
```

单条 Bad Case 可独立重放：

```powershell
uv run python scripts/run_evaluation_v2.py --sample-id gift-water
```

`evaluation/reports/evaluation_v2.md` 中的指标均提供 numerator / denominator。当前样本全部是 `UNREVIEWED`，其中淘宝样本是脱敏 fixture 回放；因此不得将报告中的 accuracy 写成真实平台或人工准确率。`evaluation_v2_regression_policy.json` 只保护机器一致性回归。

### 阶段 3 Hybrid Parser 调试

阶段 3 的 Parser 会在 `ParseResult` 中记录 `parser_source`、`reason_code`、`candidate_count` 和 LLM schema 状态。运行阶段3报告：

```powershell
uv run python scripts/run_hybrid_parser_optimization.py
```

规则层失败不会被隐藏；报告会列出失败 sample、Bad Case 分类、规则/LLM 归属及优化前后指标。FakeLLMProvider 只验证结构化输出和 fail-closed 路径，不代表线上模型表现。

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

## 本地设备桥接调试

后端启动后，Android Debug 构建默认连接 `http://10.0.2.2:8000`，设备 ID 为 `android-default`。主要接口：

```text
POST /observations?device_id=android-default
POST /devices/android-default/actions
GET  /devices/android-default/actions/next
POST /devices/android-default/action-results
GET  /devices/android-default
```

动作必须携带后端当前最新的 `observation_id`。动作入队后，如果设备先上传了更新观察，后端会将旧动作标记为 `STALE_OBSERVATION`，不会下发。生产或非本机环境必须配置 `DEVICE_SHARED_TOKEN`、TLS 和正式设备身份机制；Debug 明文 HTTP 配置不得复制到 release。

CI 配置位于 `.github/workflows/ci.yml`，覆盖 Python 3.12 后端测试、两个 Android 工程的测试和 Debug 构建，以及浏览器 Mock Web E2E。只有远端 Actions 实际成功后，才能声明 CI 通过。

## 桌面浏览器运行

桌面端使用可选 Playwright 依赖和 Chromium headless shell：

```powershell
uv sync --extra browser
uv run playwright install chromium-headless-shell
uv run python scripts/run_browser_mock.py
```

`BrowserRuntime` 实现现有 `ActionDevice` 接口，支持观察 DOM/ARIA 节点、点击、输入、滚动、返回、等待和安全停止。默认执行本地 Mock Web；真实平台需要显式设置 allowed hosts，并单独开发平台 Adapter。不要把真实账号、Cookie、截图或未脱敏 HTML 写入仓库。

### 网页只读 fixture 采集

阶段15提供通用网页 Adapter 和脱敏采集工具。采集公开页面时，必须限制允许域名，并将输出写入项目目录：

```powershell
uv run python scripts/capture_web_fixture.py `
  https://example.com/search `
  evaluation/fixtures/web/example_search.json `
  --platform-id example `
  --allowed-host example.com
```

需要人工导航时使用 `--headed --interactive`。工具不会保存 Cookie、浏览器状态、截图或原始 HTML；真实平台接入仍需先确定平台，再在专用 Adapter 中配置选择器。

淘宝页面结构 fixture 回放：

```powershell
uv run python scripts/run_taobao_fixture_replay.py
```

报告写入 `evaluation/reports/phase16_taobao_fixture_replay.json`。该命令只读取项目内脱敏 fixture，不访问实时淘宝页面。

## 阶段 4 Android Runtime 验证

阶段 4 的 bridge retry、action lifecycle、action_id 去重和 instrumented test harness 已加入，但 Runtime 验证必须在 Emulator/Device 上执行。当前本机没有 Emulator、AVD 或 system image，因此状态是 `BLOCKED`，详见 [android_runtime_validation.md](../evaluation/reports/android_runtime_validation.md)。不能用 APK build 或 JVM test 替代 Runtime Verified。

## 阶段 5 多平台 Adapter 验证

统一平台扩展入口为 `PlatformAdapter`/`BasePlatformAdapter`：

```text
Runtime → Observation → PlatformAdapter → NormalizedProduct → ComparisonEngine / Agent
```

Taobao、JD、Meituan 的平台差异应留在各自 Adapter；JD/美团当前使用仓库内脱敏 fixture，不是实时网站连接器。阶段5回归命令：

```powershell
uv run pytest backend/tests/test_multi_platform_adapters.py backend/tests/test_comparison.py backend/tests/test_taobao_adapter.py backend/tests/test_mock_adapter.py backend/tests/test_web_adapter.py -q
uv run pytest -q
```

报告见 [multi_platform_adapter_validation.md](../evaluation/reports/multi_platform_adapter_validation.md)。

## 阶段 6 设备会话可靠性

设备会话通过 `SessionStore` 抽象管理，development 默认使用 SQLite，测试使用 InMemory：

```text
SESSION_STORE_BACKEND=sqlite
SESSION_STORE_PATH=data/device_sessions.sqlite3
SESSION_MAX_QUEUE_SIZE=32
SESSION_LEASE_TIMEOUT_SECONDS=30
SESSION_DEVICE_TIMEOUT_SECONDS=60
SESSION_MAX_LEASE_RETRIES=3
```

会话动作通过 `lease_next_action()` 获取租约；租约过期可恢复，已完成动作不会再次 lease，观察版本变化会清理为 `STALE_OBSERVATION`。队列满时返回 429。阶段6验证：

```powershell
uv run pytest backend/tests/test_session_store.py -q
uv run pytest -q
```

报告见 [session_store_validation.md](../evaluation/reports/session_store_validation.md)。SQLite 是本地单体持久化，不是 Redis 或分布式任务队列。

## Android 构建

```powershell
F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0\bin\gradle.bat test --offline --no-daemon --console=plain
F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0\bin\gradle.bat assembleDebug --offline --no-daemon --console=plain
```

Android 和 Mock App 构建可能出现 Gradle 弃用、SDK XML 兼容和 Android API 弃用警告。没有物理设备时不得声称完成 runtime 验证。

## 环境策略

不要自动安装系统级软件。缺少工具时记录准确的 `MISSING` 或 `UNKNOWN`，并通过批准的 Windows/Android 开发渠道处理。

## Windows 工具与下载路径约定

项目相关工具和缓存默认放在 `F:\newinstall`，项目文件只放在 `F:\projects_2027\PriceSight` 或其子目录。当前已设置用户级路径：

```text
GRADLE_HOME=F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0
GRADLE_USER_HOME=F:\newinstall\gradle-user-home
ANDROID_HOME / ANDROID_SDK_ROOT=F:\newinstall\android_sdk
ANDROID_USER_HOME=F:\newinstall\android-user-home
UV_CACHE_DIR=F:\newinstall\uv-cache
PIP_CACHE_DIR=F:\newinstall\pip-cache
PLAYWRIGHT_BROWSERS_PATH=F:\newinstall\playwright-browsers
npm_config_cache=F:\newinstall\npm-cache
```

新增下载或工具依赖时，优先使用上述 F 盘路径；如果工具不支持修改路径，先向用户说明并询问。设置用户级变量后，需要重启终端或 Codex 才能让新进程完全继承。

## 增量开发规则

每个阶段都必须保留健康检查、增加 focused tests、运行相关验证、更新 `docs/PHASE_STATUS.md`，并且不能把未来功能仅写在 README 中冒充已实现。
