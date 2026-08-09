package com.pricesight.mockshopping

data class MockProduct(
    val id: String,
    val title: String,
    val price: String,
    val scenario: String,
)

object MockCatalog {
    val products: List<MockProduct> = buildList {
        add(MockProduct("cola-a", "可口可乐 500ml 2瓶 | Mock店A", "¥12.90", "duplicate-name"))
        add(MockProduct("cola-b", "可口可乐 500ml 2瓶 | Mock店B", "¥11.90", "duplicate-name"))
        add(MockProduct("cola-330", "可口可乐 330ml 6罐", "¥19.90", "multi-spec"))
        add(MockProduct("combo", "双人套餐 组合装", "¥29.90", "combo"))
        for (index in 4..29) {
            add(MockProduct("long-$index", "长列表测试商品 $index 500ml", "¥${index + 5}.90", "long-list"))
        }
    }
}
