# 阶段16报告——淘宝页面结构只读回放

更新时间：2026-08-09

## 目标

将用户提供的淘宝搜索页面结构 fixture 转换为统一浏览器 `Observation`，再使用淘宝 Adapter 的常规网页商品抽取路径完成可重复的只读回放。

## 已完成

- 将搜索框、搜索 Tab、搜索按钮、商品列表和分页信息转换为标准 `ObservationNode`。
- 将淘宝页面来源域名 `uland.taobao.com` 纳入显式 allowlist。
- 商品卡片使用淘宝 Adapter 的配置化商品结果前缀和 content description。
- 回放过程不执行点击、输入、导航、加购、下单或支付。
- 新增 `scripts/run_taobao_fixture_replay.py`，生成机器可读报告。

## 实测回放结果

报告文件：[phase16_taobao_fixture_replay.json](../evaluation/reports/phase16_taobao_fixture_replay.json)

```text
模式：taobao_sanitized_fixture_replay
真实页面访问：否
外部副作用：否
搜索词：iphone17
页码：1
存在下一页：是
识别成功：是
商品数：2
价格：5999.00、5999.00
选择器角色：product_result、search_input、search_submit
```

## 验证

```text
101 passed, 1 warning
python -m compileall -q backend/app backend/tests evaluation scripts：通过
git diff --check：通过
```

警告仍为既有 Starlette/httpx `TestClient` 弃用提示，不影响测试结果。

## 结论与限制

本阶段证明了：用户提供的结构化淘宝页面可以进入统一 Observation 和网页 Adapter 抽取链路。它仍然不是实时网页测试；当前淘宝选择器来自脱敏 fixture 的语义契约，尚未通过真实浏览器 DOM/ARIA 观察验证。报告中的价格只代表 fixture 内容，不代表当前淘宝价格。

下一步只有在获得可访问的公开页面 Observation 后，才能验证真实选择器、页面变化处理和真实网页只读稳定性。
