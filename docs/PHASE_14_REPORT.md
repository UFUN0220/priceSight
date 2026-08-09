# 阶段14——桌面浏览器 Runtime 与 Mock Web

完成日期：2026-08-09

## 目标

在不依赖物理 Android 设备的前提下，为现有 Workflow、Agent、Action Harness 和 SafetyGuard 增加桌面浏览器执行端，使项目能够完成可重复的电脑端只读商品流程。

## 已实现

- 新增 `BrowserRuntime`，实现统一 `ActionDevice` 接口。
- 使用 Playwright 从 DOM/ARIA 和可交互节点生成统一 Observation。
- 支持点击、输入、滚动、返回、等待和安全停止。
- 复用现有 `TargetMatcher`、`ActionExecutor`、`WorkflowEngine` 和 `SafetyGuard`。
- 新增 `RuntimeSession` 和 `TaskOrchestrator`，隔离 Runtime 类型与任务编排。
- 新增 allowed-host 检查，跨域导航会停止。
- 新增 `mock-shopping-web/index.html`。
- 新增 `scripts/run_browser_mock.py`，覆盖搜索、输入、结果、商品详情、价格读取和订单确认前安全停止。
- 新增 `.github/workflows/ci.yml` 浏览器 E2E job。
- Playwright/Chromium 作为可选依赖，不影响无浏览器环境的后端测试。

## 实际验证

```text
Backend: 91 passed, 1 existing Starlette/httpx deprecation warning
Browser Runtime tests: 2 passed
Python compileall: passed
Mock Web Chromium E2E: passed
Price: 10.90
Safety status: SAFETY_BLOCKED
Order submitted: false
```

## 安全边界

- 只测试本地 Mock Web，未接入真实购物平台。
- 订单确认页面只用于验证安全停止，不执行提交。
- 真实网站必须手动登录，禁止自动输入密码和绕过 CAPTCHA。
- URL、HTML、截图和页面文本可能包含隐私信息，保存 fixture 前必须脱敏。

## 未完成

- 真实购物网站的页面识别和平台 Adapter。
- 真实网站只读搜索、规格、价格和促销验证。
- Browser Context 的持久化登录、断线恢复和任务并行控制。
- coverage、lint、类型检查和远端 CI 成功记录。

## 运行命令

```powershell
uv sync --extra browser
uv run playwright install chromium-headless-shell
uv run python scripts/run_browser_mock.py
```
