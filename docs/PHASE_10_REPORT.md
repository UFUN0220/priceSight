# 阶段10报告——离线多来源商品比较核心

更新时间：2026-08-08

## 范围决定

由于没有物理设备和真实平台 fixture，本阶段实现可复用的多来源比较核心和隔离 synthetic source adapter，不声称 Meituan、JD 或 Taobao 集成。

## 已实现

- normalized requirement、offer、final price 和 comparison result DTO。
- 支持商品名称别名、规格和内容单位的保守匹配。
- 少于两个 offer 可比时拒绝强行推荐。
- 只使用明确解析出的优惠券/促销折扣计算最终价。
- 以 platform、store、normalized product、specification 为 key 的过期 OfferCache。
- `fixture-store-a`、`fixture-store-b` 等价规格来源和规格不匹配来源。
- 跨来源集成测试和离线 runner。

## 验证

```text
后端：68 passed，1 个 warning
可比价格：10.90、11.80
推荐来源：fixture-store-a
第一次 cache hits：0
第二次 cache hits：2
规格不匹配：comparable=false，不强行推荐
physical device：未连接
```

## 未声称

没有实现或联系 Meituan、JD、Taobao；没有使用真实账号、网络、订单、支付或真实 Accessibility Tree。

## 完成判断

比较模型、保守匹配、最终价计算、缓存边界、synthetic 跨来源测试、报告和文档均已完成，未伪造真实平台支持。
