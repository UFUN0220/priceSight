# PriceSight 定向补强最终报告

## 1. 修改了什么

- 扩展现有 `Quantity`、`ProductSpecification`、`ParseResult` 和平台标准化 DTO，保留 raw/normalized/unit/pack/total quantity、状态与 evidence。
- 强化 quantity parser：支持数量在容量前、`×/*/x`、容器前缀、连包/连装和中英文容器单位；赠品仍与主购买量分离。
- 重写 `PriceParser` 的候选提取与排名，保存 source text、node/selector、Decimal normalization、parser 和 confidence；对区间、会员价、起售价和冲突候选 abstain。
- 新增 `PricingEngine`/`PricingRule`，以 Decimal 计算直接券、门槛、组合/多件规则和配送费；条件无法确认时返回 `UNRESOLVED`。
- `WebPlatformAdapter`、`MockShoppingAdapter` 和比较层接入价格证据、状态和 comparison confidence/reason。
- 新增统一 write-once baseline 与 final evaluation 命令及机器/Markdown 结果；新增 Agent 边界、核心代码地图和简历证据文档。

## 2. 为什么修改

当前主要失败集中在 `bulk`、`sku_mixed_text`、`coupon_price`、`gift` 和价格动态/歧义。问题本质是页面事实、解析结果和推导价格没有足够清晰的边界；继续增加 Runtime 周边功能不能解决这些失败，也会放大错误自信输出。

## 3. baseline → final 指标

基线冻结于 `evaluation/results/baseline.json`，final 见 `evaluation/results/final.json`。没有修改评测答案、DEV/HOLDOUT membership 或 metric contract。

| Scope | CORE | STRICT | Quantity | Specification | Displayed price | Effective price |
| --- | --- | --- | --- | --- | --- | --- |
| DEV | 5/32 → 5/32 | 2/32 → 2/32 | 23/32 → 23/32 | 14/32 → 14/32 | 8/31 → 8/31 | 0/10 → 0/10 |
| HOLDOUT | 0/8 → 0/8 | 0/8 → 0/8 | 3/8 → 3/8 | 3/8 → 3/8 | 2/6 → 2/6 | 0/2 → 0/2 |
| ALL | 16/96 → 16/96 | 12/96 → 12/96 | 69/92 → 69/92 | 49/96 → 49/96 | 18/85 → 18/85 | 1/24 → 1/24 |
| HUMAN | 5/40 → 5/40 | 2/40 → 2/40 | 26/40 → 26/40 | 17/40 → 17/40 | 10/37 → 10/37 | 0/12 → 0/12 |

指标未提升不是被隐藏的失败：当前 HUMAN raw text 大量没有可复核价格证据，且重建来源不是 live capture；新增 parser cases 由单元测试验证，不能反写冻结评测来制造提升。

## 4. 测试结果

- Python 质量门禁：Ruff、`mypy backend/app`、compileall、pre-commit 和 coverage 分项均通过；172 passed，branch coverage 85%，超过 80% 门槛。
- Android client：离线 `test` 和 `assembleDebug` 通过。
- Mock Shopping App：离线 `test` 和 `assembleDebug` 通过。
- Browser Mock：成功读取 `10.90`，订单确认页触发 `SAFETY_BLOCKED`，`order_was_submitted=false`。
- Python Mock E2E：task success，action success rate 1.0，SafetyGuard 正确阻断。
- Mock Adapter：成功/详情/未知平台 graceful failure 均通过。
- `uv run python scripts/build_improvement_evaluation.py`：成功生成 DEV/HOLDOUT/ALL/HUMAN 与 Bad Case delta。
- `git diff --check`：最终验收时执行并通过。

## 5. 真实环境验证边界

`REAL_APP_NOT_ESTABLISHED`：本机 `adb devices` 未发现可用 Emulator/物理设备，本轮没有运行真实购物 App。现有淘宝证据仅是此前一次公开网页只读 smoke；JD/美团 live、真实 App 登录/风控/优惠券/支付均未验证。Mock、fixture、reconstructed human replay 与 live read-only evidence 保持分离。

## 6. 尚未解决的问题

- HOLDOUT CORE/STRICT 仍为 0/8，泛化仍是 `LIMITED`。
- HUMAN effective price 仍为 0/12；复杂券、会员身份、配送费和动态价格缺少足够合法 evidence。
- 商品身份和多 SKU 标题仍需要更强的语义候选模型；FakeLLM 不能证明线上模型效果。
- 真实 Android App、真实平台稳定性、网络重连、生产吞吐和长期价格稳定性未验证。

## 7. 当前适合的简历描述

可以写：面向 Android Accessibility/Browser DOM 的安全模式 Computer-Use Agent；结构化 Observation 压缩；Rule→Workflow→LLM 混合决策；action grounding 与 stale observation 拒绝；价格 evidence 与 Decimal effective-price pipeline；Mock Android/Browser E2E、安全阻断、自动化评测与覆盖率门禁。

不能写：真实跨平台高准确率、JD/美团/淘宝 Android 已打通、线上有效价格高准确率、自动真实下单支付、HOLDOUT 泛化已解决。

## 8. 当前最危险的 10 个面试问题

1. 为什么 displayed price 和 effective price 必须分开？
2. 满减门槛在什么条件下可以计算，什么时候必须 `UNRESOLVED`？
3. 为什么不能直接取 DOM 中最低价格？
4. `550ml×12`、`12×330ml` 和 `买二赠一` 如何区分？
5. 如何避免 SKU 存储容量或型号数字被当成商品数量？
6. FakeLLM evaluation 为什么不能当作线上模型准确率？
7. CORE 与 STRICT 的分母和判定边界分别是什么？
8. 为什么 HOLDOUT 仍为 0/8，为什么不能修改答案让它变绿？
9. Android Mock App 的闭环证据和真实购物 App 证据差在哪里？
10. stale Observation、SafetyGuard 和价格 abstention 如何共同防止错误自信执行？

## 9. Final Remote Freeze

- Repository：`UFUN0220/priceSight`
- Branch：`master`
- Commit：`c5ad99306e0ffcafe7b1f9ee5cf789aeb9a2a051`
- Workflow：`项目持续集成`
- Run：`31412588211`（trigger：`push`）
- Python 测试与覆盖率：`172 passed`，branch coverage `85%`，门槛 `80%`，通过。
- Python 质量门禁、Browser Mock Web E2E、Android client、Mock Shopping App：全部通过。
- HOLDOUT/HUMAN 指标与 baseline→final 一致；HUMAN core `5/40`、strict `2/40` 未因 provenance/path 问题归零。

本报告只声明工程链路和该 commit 的远端 CI 已验证；不声明真实 App 泛化、生产级价格识别或真实优惠价格准确计算。
