# 阶段15报告——真实网页 Adapter 基础

更新时间：2026-08-09

## 目标

为桌面浏览器 Runtime 建立真实购物网站只读接入的通用基础，同时保持平台选择器、网页证据和安全边界彼此隔离。本阶段不访问真实购物网站，不使用真实账号，也不执行加购、下单或支付。

## 已完成

- 新增 `WebPlatformAdapter`，基于统一 `Observation` 提供网页平台识别、页面识别、商品/价格/优惠抽取和平台选择器提示。
- 新增 `WebSelectorConfig`，把 resource id、content description 和页面动作标识作为可配置项，避免把具体网站选择器写进通用 Browser Runtime。
- 新增网页证据模型与脱敏逻辑，移除 URL 查询参数和片段，并对邮箱、手机号及长数字标识脱敏。
- 新增 `scripts/capture_web_fixture.py`，支持在允许域名范围内采集脱敏 Observation fixture；默认不保存 Cookie、浏览器状态、截图、原始 HTML 或密码。
- 为网页 Adapter、网页证据脱敏和跨来源比较增加自动化测试。
- 接入用户提供的淘宝 `iphone17` 结构化搜索 fixture：保留 10 条商品、价格、店铺、地区和商品特征，过滤埋点信息及商品跳转链接。
- 新增 `extract_search_fixture` 回放入口，将结构化商品转换为统一 `PlatformProduct`，并继续使用现有商品/规格解析器。
- 接入用户补充的页面结构 fixture：验证搜索词、Tab 选择状态、搜索按钮和分页字段，并通过 `extract_structured_page_fixture` 回放其中 2 条商品。

## 验证结果

本次执行结果：

```text
100 passed, 1 warning
python -m compileall -q backend/app backend/tests evaluation scripts：通过
```

淘宝相关聚焦测试共 5 项，网页相关回归测试全部通过。唯一警告为既有 Starlette/httpx `TestClient` 弃用提示，不影响测试结果。

## Fixture 采集用法

仅允许写入项目目录，并且必须显式提供允许域名：

```powershell
uv run python scripts/capture_web_fixture.py `
  https://example.com/search `
  evaluation/fixtures/web/example_search.json `
  --platform-id example `
  --allowed-host example.com
```

需要人工在浏览器中完成公开页面导航时，可使用 `--headed --interactive`。采集前应确认页面不含个人隐私、登录信息、Cookie、支付信息或验证码内容。

## 尚未完成

- 已建立淘宝专用 Adapter 骨架、显式域名白名单和合成 fixture 回放；尚未把任何未经验证的真实淘宝 DOM 选择器写入代码。
- 尚未针对 Meituan、JD 或其他平台实现专用 Adapter。
- 淘宝公开页面检查被当前浏览器安全策略拦截，因此本阶段没有真实淘宝网页结构结论。
- 尚未执行真实网页只读回放，因此没有真实平台成功率、价格准确率或延迟指标。
- 线上 CI 仅具备配置基础，必须推送到远端仓库并等待 GitHub Actions 实际运行后，才能报告 CI 结果。

## 下一步输入

下一步需要在允许访问淘宝公开页面的条件下，采集并人工审核脱敏 Observation fixture，再据此替换当前未验证的选择器契约。接入时仍保持 SAFE MODE，只读取公开商品、规格、价格和优惠信息；遇到登录、验证码、支付、下单或身份验证页面立即停止。
