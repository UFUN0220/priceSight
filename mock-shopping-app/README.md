# Mock 购物应用

这是用于安全模式 E2E 测试的本地受控 Android 购物应用，不是真实商店，没有网络、账号、订单或支付集成。

## 包含页面与场景

- 首页、搜索、商品列表、商品详情和嵌套规格弹窗；
- 优惠券页、购物车、订单确认页和模拟支付页；
- 重复商品名、多规格、组合装、30 项长列表、动态加载按钮和空文本 clickable 节点。

## 构建与测试

```powershell
gradle test --offline --no-daemon --console=plain
gradle assembleDebug --offline --no-daemon --console=plain
```

订单确认和支付页面只用于验证确定性 `SafetyGuard` 停止逻辑，应用不会执行真实订单或支付。
