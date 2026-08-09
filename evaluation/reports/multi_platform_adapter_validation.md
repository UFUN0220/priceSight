# 阶段 5：多平台 Adapter 架构验证报告

验证日期：2026-08-09  
验证范围：统一 PlatformAdapter、Taobao/JD/Meituan 脱敏 fixture、单位价比较回归  
结论：**FIXTURE_VERIFIED / MOCK_VERIFIED；真实 JD、真实美团和实时淘宝仍为 NOT_VERIFIED。**

## 1. 目标与边界

本阶段验证“新增平台主要增加 Adapter，不需要复制 Runtime，也不需要修改 Agent 或核心 Workflow”。统一链路为：

```text
Runtime
  → Observation
  → PlatformAdapter
  → NormalizedProduct
  → ComparisonEngine / Agent
```

本阶段没有访问真实 JD、真实美团或实时淘宝页面，没有登录、下单、付款、验证码处理或反爬绕过。所有 JD/美团数据均为仓库内脱敏 fixture；Taobao 复用既有浏览器观察和脱敏 fixture 回放。

## 2. 统一接口

`backend/app/platform/base.py` 新增 `BasePlatformAdapter`，并扩展 `PlatformAdapter` protocol：

- `identify_page(observation)`：识别页面类型；
- `parse_products(observation)`：统一商品列表入口，兼容已有 `extract_products()`；
- `parse_product_detail(observation)`：统一详情入口，兼容已有 `extract_product()`；
- `normalize_product(product)`：输出平台无关的 `NormalizedProduct`；
- `safety_boundary(observation)`：对订单确认/支付页面和安全词进行确定性停止。

`NormalizedProduct` 至少保留：平台、标题、基础价、有效价、数量、规格、卖家/店铺、商品 ID/URL、置信度和抽取来源。Taobao 仍由 `TaobaoPlatformAdapter → WebPlatformAdapter` 提供原有选择器 fallback、页面状态和商品证据逻辑，没有复制 Runtime。

## 3. 平台 Adapter

| Adapter | 代码位置 | 数据来源 | 结果等级 | 真实平台状态 |
|---|---|---|---|---|
| Taobao | `backend/app/platform/taobao/adapter.py` | 已有网页/结构化脱敏 fixture | FIXTURE_VERIFIED | NOT_VERIFIED |
| JD | `backend/app/platform/jd/adapter.py` | `backend/tests/fixtures/platform/comparison/jd.json` | FIXTURE_VERIFIED | NOT_VERIFIED |
| Meituan | `backend/app/platform/meituan/adapter.py` | `backend/tests/fixtures/platform/comparison/meituan.json` | FIXTURE_VERIFIED | NOT_VERIFIED |

JD 与美团 Adapter 复用受控的 Observation/Fixture 合同；它们不是实时网站连接器，也不代表真实页面 selector 已稳定。

## 4. 比价规则验证

`ComparisonEngine` 现在通过统一 `parse_products()` 和 `normalize_product()` 取数，并使用：

1. 规格与数量的保守匹配；
2. 显式优惠后的 `effective_price`；
3. 规格中的归一化内容量和包装数量计算 `effective_unit_price`；
4. 单位价相同或接近时使用 confidence 作为并列决策因子；
5. 无法计算单位价时不强行给出推荐。

JD 与美团 fixture 都是“可口可乐 500ml×2瓶”，分别为 ¥11.80 与 ¥10.00。回归测试确认美团有效单位价更低并被推荐；测试同时确认抽取来源分别为 `jd_fixture` 与 `meituan_fixture`，没有把 fixture 写成实时数据。

## 5. 测试与可复现命令

### VERIFIED

- Python 编译：`uv run python -m compileall -q backend/app backend/tests scripts`。
- 后端全量测试：`122 passed, 0 failed, 1 warning`。
- `git diff --check`：通过，无空白错误。

### FIXTURE_VERIFIED

- Taobao 统一接口和既有网页 Adapter 回放：通过；未访问实时淘宝。
- JD fixture 商品列表解析、标准化和来源标记：通过。
- Meituan fixture 商品列表解析、标准化和来源标记：通过。
- 订单确认 fixture 的 `safety_boundary()`：返回 `SafetyDecision.STOP`。

### MOCK_VERIFIED

- `backend/tests/test_multi_platform_adapters.py` 及既有比较/平台测试：`28 passed`。
- 跨平台比较回归覆盖：统一接口、标准化字段、有效单位价、置信度字段、来源标识和安全停止。

### BUILD_ONLY

- 本阶段未新增 Android 或 Mock App 构建结果。阶段 4 的 Android Runtime 仍按既有报告标记为 BLOCKED/NOT_VERIFIED；APK 构建不能替代 Runtime Verified。

### NOT_VERIFIED

- 实时淘宝 DOM/ARIA selector 的完整项目 runner 链路；
- 真实 JD 页面只读解析；
- 真实美团页面只读解析；
- 真实网络延迟、跨平台在线成功率和生产级吞吐；
- 人工复核的跨平台准确率。

## 6. 扩展性证据与剩余问题

阶段 5 的 Adapter/比较改动没有修改 `backend/app/runtime`、`backend/app/agent` 或 `workflows/`。新增 JD/美团主要涉及各自 Adapter、fixture 和回归测试；Runtime、Observation DTO、Agent 和核心 Workflow 继续复用。该结论是仓库代码结构和自动化回归证据，不是线上平台验证结果。

剩余 P0 是真实平台验证条件和脱敏样本：需要允许的只读浏览器会话、人工确认的 fixture、页面状态覆盖和独立安全审查。具备条件前，不应声称“已支持真实 JD/美团”或跨平台线上准确率。
