package com.pricesight.androidclient

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RetryPolicyTest {
    @Test
    fun retryBoundaryIsBounded() {
        val policy = ExponentialBackoffRetryPolicy(randomUnit = { 0.5 })

        assertTrue(policy.shouldRetry(0))
        assertTrue(policy.shouldRetry(2))
        assertTrue(!policy.shouldRetry(3))
        assertEquals(250L, policy.delayMs(0))
        assertEquals(500L, policy.delayMs(1))
        assertEquals(1_000L, policy.delayMs(2))
    }

    @Test
    fun jitterStaysWithinConfiguredBoundary() {
        val low = ExponentialBackoffRetryPolicy(jitterRatio = 0.2, randomUnit = { 0.0 })
        val high = ExponentialBackoffRetryPolicy(jitterRatio = 0.2, randomUnit = { 1.0 })

        assertEquals(200L, low.delayMs(0))
        assertEquals(300L, high.delayMs(0))
    }
}
