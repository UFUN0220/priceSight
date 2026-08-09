# 阶段8报告——Mock Shopping App 与完整安全模式 E2E

更新时间：2026-08-08

## 范围

建立受控 Mock Shopping App 和可重复的后端 E2E，覆盖搜索、商品选择、规格、优惠、购物车和订单确认前的安全停止。不使用真实商店、账户、订单、支付或物理设备。

## 已实现

- `mock-shopping-app/`：API34/Kotlin 应用，包含首页、搜索、商品列表、商品详情、嵌套规格弹窗、优惠券、购物车、订单确认和模拟支付页。
- 重复商品名、多规格、组合装、30 项长列表、动态加载和空文本 clickable 节点场景。
- Python `MockShoppingDevice`，每次 observation 都经过 `ObservationCompressor`。
- 搜索 Workflow → Agent handoff → FakeLLM 商品选择 → fresh grounding → 规格/优惠/购物车 → 最终价 → `SafetyGuard` 停止。
- E2E metrics model 和 runner。

## 实际结果

```text
task_success：true
steps：13
retries：0
llm_calls：1
final_price：10.90
safety_result：SAFETY_STOP
raw/compressed：194 / 166，26 次压缩
```

阶段13刷新后，单次运行还记录 `action_attempts=11`、`action_success_rate=1.0`、`safety_stop_correct=true`。

## 验证

后端测试、Mock runner、Mock Shopping App 的 Gradle 测试和 assembleDebug 均曾通过。Android APK 未安装或驱动，因为没有连接物理设备。

## 限制

这是受控测试产物，不是真实平台成功率或延迟。后端 action channel 仍是注入式边界，Android runtime 尚未接通。
