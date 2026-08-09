package com.pricesight.mockshopping

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MockCatalogTest {
    @Test
    fun catalogIncludesRequiredScenarioVariations() {
        assertEquals(30, MockCatalog.products.size)
        assertEquals(2, MockCatalog.products.count { it.scenario == "duplicate-name" })
        assertTrue(MockCatalog.products.any { it.scenario == "multi-spec" })
        assertTrue(MockCatalog.products.any { it.scenario == "combo" })
        assertEquals(26, MockCatalog.products.count { it.scenario == "long-list" })
    }
}
