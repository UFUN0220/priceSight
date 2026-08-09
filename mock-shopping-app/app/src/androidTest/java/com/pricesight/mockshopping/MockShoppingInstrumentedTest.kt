package com.pricesight.mockshopping

import android.test.ActivityInstrumentationTestCase2
import android.view.View
import android.view.ViewGroup
import android.widget.TextView

/**
 * Device-side UI contract for the stable Mock Shopping pages.
 * This test must run on an emulator/device; JVM tests do not replace it.
 */
class MockShoppingInstrumentedTest : ActivityInstrumentationTestCase2<MainActivity>(MainActivity::class.java) {
    private lateinit var activity: MainActivity

    override fun setUp() {
        super.setUp()
        activity = getActivity()
        instrumentation.waitForIdleSync()
    }

    fun testSearchDetailCartAndOrderConfirmationBoundary() {
        click("search")
        val input = findByDescription("search_input")
        assertNotNull("search input must be present", input)
        instrumentation.runOnMainSync { (input as android.widget.EditText).setText("可口可乐500ml") }
        click("search_submit")
        click("product_result")
        assertNotNull("detail page title must be visible", findText("商品详情"))
        click("add_to_cart")
        click("checkout")
        assertNotNull("order confirmation page must be visible", findText("订单确认页（仅用于测试 SafetyGuard）"))
        assertNotNull("submit button must remain the safety boundary", findByDescription("submit_order"))
    }

    fun testBackAndLongListPagesAreReachable() {
        click("long_list_demo")
        assertNotNull("result page must be visible", findText("商品列表"))
        activity.runOnUiThread { activity.onBackPressed() }
        instrumentation.waitForIdleSync()
        assertNotNull("home page must be restored", findText("Mock Shopping 首页"))
    }

    private fun click(description: String) {
        val view = findByDescription(description)
        assertNotNull("missing view: $description", view)
        instrumentation.runOnMainSync { view!!.performClick() }
        instrumentation.waitForIdleSync()
    }

    private fun findText(text: String): View? = findView(activity.window.decorView) {
        it is TextView && it.text?.toString() == text
    }

    private fun findByDescription(description: String): View? = findView(activity.window.decorView) {
        it.contentDescription?.toString() == description
    }

    private fun findView(view: View, predicate: (View) -> Boolean): View? {
        if (predicate(view)) return view
        if (view is ViewGroup) {
            for (index in 0 until view.childCount) {
                findView(view.getChildAt(index), predicate)?.let { return it }
            }
        }
        return null
    }
}
