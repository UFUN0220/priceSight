# 阶段 7：CI、Coverage、Lint、Typing 与最终验收报告

验证日期：2026-08-09  
结论：**Python quality/test 门禁 VERIFIED；Android test/build 本地 VERIFIED；Android lint 本地因离线依赖缺失 BLOCKED；远端 CI NOT_VERIFIED。**

## 1. CI 结构

`.github/workflows/ci.yml` 已拆分为四个明确 job：

- `python-quality`：Ruff、mypy、compileall、pre-commit；
- `python-test`：pytest、分支 coverage；
- `browser-test`：Mock Web Chromium E2E；
- `android-test-build`：Android Client 和 Mock Shopping App 的 unit test、`lintDebug`、`assembleDebug`。

Python 与浏览器 job 使用 Python 3.12；Android job 使用 JDK 17、Android 34 和 Gradle 9.7。

## 2. Coverage 基线与门槛

首次安装 pytest-cov/coverage 后测得：

| 范围 | 实测覆盖率 | 门槛 |
|---|---:|---:|
| `backend/app`，branch coverage | 85% | 80% |

门槛依据当前 132 个测试和真实覆盖率测量设置，不是追求 90% 的不现实指标。重点模块当前覆盖：SafetyGuard 96%、Product/Quantity/Hybrid Parser 92–97%、DeviceSession 92%、Action Executor 87%、Platform Mock/Taobao 80–92%、TaskOrchestrator 已增加回归覆盖。Browser Runtime 的可选真实浏览器分支仍较低，未通过排除模块伪造整体数字。

## 3. Python quality

### VERIFIED

- `uv run pytest -q`：`132 passed`。
- `uv run coverage run --branch -m pytest -q`：通过。
- `uv run coverage report --fail-under=80`：通过，实测 85%。
- `uv run ruff check backend/app backend/tests scripts`：通过。
- `uv run mypy backend/app --show-error-codes`：`Success: no issues found in 79 source files`。
- `uv run python -m compileall -q backend/app backend/tests evaluation scripts`：通过。
- `uv run pre-commit run --all-files`：Ruff 和 Python compile 两个轻量 hook 均通过。

## 4. Android 验证

### VERIFIED / BUILD_ONLY

- Android Client：unit test 通过，`assembleDebug` 通过。
- Mock Shopping App：unit test 通过，`assembleDebug` 通过。
- CI 已把两个项目统一纳入 `android-test-build` job，并显式运行 `lintDebug`。

### BLOCKED / NOT_VERIFIED

本机执行两个项目的 `lintDebug --offline` 均因缺少缓存依赖失败：

```text
Could not resolve com.android.tools.lint:lint-gradle:31.5.2
No cached version ... available for offline mode
```

CI 使用联网 runner，可下载该依赖；但当前没有远端 Actions 运行记录，因此不能声称 CI lint 已通过。SDK 仍出现 XML v4/v3 工具版本提示；本阶段未强行替换 SDK 工具链，记录为技术债。Gradle 10 deprecation 也未通过大版本升级处理，以避免破坏 AGP/Kotlin 兼容性。

Android Runtime 仍沿用阶段4结论：无 Emulator/AVD，不能写成 Runtime Verified。

## 5. 弃用警告处理

Starlette 1.5 在 Python 3.12 环境下提示优先安装 `httpx2`。当前可解析的 `httpx2` 版本要求 Python 3.14，不满足项目 Python 3.12 约束，因此没有强行升级或改变运行时依赖。项目对该已知上游警告加入精确的 pytest filter，并在本地测试中确认输出清洁；该依赖兼容问题保留为技术债。

Android Kotlin 的未使用 `reportResponse` 局部变量已安全清理。Gradle deprecation 和 SDK XML 版本差异没有伪装成已解决。

## 6. 本地一条验证入口

Python 质量、测试和覆盖率：

```powershell
uv sync --extra dev
uv run python scripts/run_quality_gate.py
```

Android 分别执行：

```powershell
F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0\bin\gradle.bat test lintDebug assembleDebug --offline --no-daemon --console=plain
```

若本机未缓存 `lint-gradle:31.5.2`，应记录 BLOCKED，不能用 assembleDebug 替代 lint 或 Runtime 结果。
