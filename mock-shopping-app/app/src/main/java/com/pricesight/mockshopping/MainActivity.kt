package com.pricesight.mockshopping

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class MainActivity : Activity() {
    private enum class Page { HOME, SEARCH, RESULTS, DETAIL, COUPONS, CART, ORDER_CONFIRM, PAYMENT }

    private var page = Page.HOME
    private var query = ""
    private var selectedProduct: MockProduct = MockCatalog.products.first()
    private var selectedSpec = ""
    private var couponClaimed = false
    private lateinit var root: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        render()
    }

    override fun onBackPressed() {
        page = when (page) {
            Page.HOME -> return super.onBackPressed()
            Page.SEARCH -> Page.HOME
            Page.RESULTS -> Page.SEARCH
            Page.DETAIL -> Page.RESULTS
            Page.COUPONS -> Page.DETAIL
            Page.CART -> Page.DETAIL
            Page.ORDER_CONFIRM -> Page.CART
            Page.PAYMENT -> Page.ORDER_CONFIRM
        }
        render()
    }

    private fun render() {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
            setBackgroundColor(Color.WHITE)
        }
        val title = TextView(this).apply {
            text = pageTitle()
            textSize = 24f
            setTextColor(Color.BLACK)
            contentDescription = "page_title"
        }
        root.addView(title, LinearLayout.LayoutParams(-1, -2))
        when (page) {
            Page.HOME -> renderHome()
            Page.SEARCH -> renderSearch()
            Page.RESULTS -> renderResults()
            Page.DETAIL -> renderDetail()
            Page.COUPONS -> renderCoupons()
            Page.CART -> renderCart()
            Page.ORDER_CONFIRM -> renderOrderConfirmation()
            Page.PAYMENT -> renderPayment()
        }
        setContentView(root)
    }

    private fun renderHome() {
        addText("可控的本地 Mock 商城，用于 Accessibility / Safety E2E。")
        addButton("搜索商品", "search") { page = Page.SEARCH; render() }
        addButton("", "empty_action") { addText("空文本 clickable 节点已触发") }
        addButton("查看长列表场景", "long_list_demo") { page = Page.RESULTS; render() }
    }

    private fun renderSearch() {
        val input = EditText(this).apply {
            hint = "输入商品，例如 可口可乐500ml"
            contentDescription = "search_input"
            setText(query)
        }
        root.addView(input, LinearLayout.LayoutParams(-1, -2))
        addButton("搜索", "search_submit") {
            query = input.text.toString()
            page = Page.RESULTS
            render()
        }
    }

    private fun renderResults() {
        addText("结果：${query.ifBlank { "全部商品" }}（含重复名称、长列表和组合装）")
        val scroll = ScrollView(this)
        val list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        MockCatalog.products.forEach { product ->
            val button = addButtonTo(list, product.title, "product_result_${product.id}") {
                selectedProduct = product
                page = Page.DETAIL
                render()
            }
            button.contentDescription = "product_result"
        }
        addButtonTo(list, "加载更多", "load_more") { addText("动态加载完成") }
        scroll.addView(list)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
    }

    private fun renderDetail() {
        addText(selectedProduct.title)
        addText("商品价格：${selectedProduct.price}")
        addButton("选择规格 ${selectedSpec.ifBlank { "未选择" }}", "spec_selector") { showSpecDialog() }
        addButton("优惠券", "coupon") { page = Page.COUPONS; render() }
        addButton("加入购物车", "add_to_cart") { page = Page.CART; render() }
    }

    private fun showSpecDialog() {
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 16, 32, 16)
        }
        lateinit var dialog: AlertDialog
        addTextTo(content, "容量：500ml")
        addButtonTo(content, "数量：2瓶", "spec_2_bottles") {
            selectedSpec = "500ml × 2瓶"
            dialog.dismiss()
            render()
        }
        addTextTo(content, "嵌套规格示例：容量 / 数量")
        dialog = AlertDialog.Builder(this)
            .setTitle("规格弹窗")
            .setView(content)
            .setNegativeButton("取消", null)
            .create()
        dialog.show()
    }

    private fun renderCoupons() {
        addText("可用优惠券：满10减2")
        addButton("${if (couponClaimed) "已领取" else "领取优惠券"}", "coupon_claim") {
            couponClaimed = true
            render()
        }
        addButton("返回商品详情", "back_to_detail") { page = Page.DETAIL; render() }
    }

    private fun renderCart() {
        addText("购物车：${selectedProduct.title} x2")
        addText("最终价 ${if (couponClaimed) "¥10.90" else "¥12.90"}")
        addButton("去结算", "checkout") { page = Page.ORDER_CONFIRM; render() }
    }

    private fun renderOrderConfirmation() {
        addText("订单确认页（仅用于测试 SafetyGuard）")
        addButton("提交订单", "submit_order") { page = Page.PAYMENT; render() }
    }

    private fun renderPayment() {
        addText("模拟支付页（禁止自动化支付）")
        addText("请输入支付密码")
    }

    private fun addText(value: String) = addTextTo(root, value)

    private fun addTextTo(parent: LinearLayout, value: String) {
        parent.addView(TextView(this).apply {
            text = value
            textSize = 16f
            setTextColor(Color.DKGRAY)
            setPadding(0, 16, 0, 16)
        }, LinearLayout.LayoutParams(-1, -2))
    }

    private fun addButton(label: String, description: String, action: () -> Unit): Button =
        addButtonTo(root, label, description, action)

    private fun addButtonTo(parent: LinearLayout, label: String, description: String, action: () -> Unit): Button {
        return Button(this).apply {
            text = label
            contentDescription = description
            gravity = Gravity.CENTER
            minHeight = 56
            setOnClickListener { action() }
            parent.addView(this, LinearLayout.LayoutParams(-1, -2))
        }
    }

    private fun pageTitle(): String = when (page) {
        Page.HOME -> "Mock Shopping 首页"
        Page.SEARCH -> "搜索页"
        Page.RESULTS -> "商品列表"
        Page.DETAIL -> "商品详情"
        Page.COUPONS -> "优惠券"
        Page.CART -> "购物车"
        Page.ORDER_CONFIRM -> "订单确认"
        Page.PAYMENT -> "模拟支付"
    }
}
