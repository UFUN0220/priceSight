package com.pricesight.androidclient

import kotlin.math.pow
import kotlin.math.roundToLong
import kotlin.random.Random

/** Bounded exponential backoff with symmetric jitter for bridge retries. */
class ExponentialBackoffRetryPolicy(
    private val baseDelayMs: Long = 250L,
    private val maxDelayMs: Long = 4_000L,
    private val maxRetries: Int = 3,
    private val jitterRatio: Double = 0.20,
    private val randomUnit: () -> Double = { Random.nextDouble() },
) {
    init {
        require(baseDelayMs > 0) { "baseDelayMs must be positive" }
        require(maxDelayMs >= baseDelayMs) { "maxDelayMs must be >= baseDelayMs" }
        require(maxRetries >= 0) { "maxRetries must be non-negative" }
        require(jitterRatio in 0.0..1.0) { "jitterRatio must be between 0 and 1" }
    }

    fun shouldRetry(retryNumber: Int): Boolean = retryNumber < maxRetries

    fun delayMs(retryNumber: Int): Long {
        require(retryNumber >= 0) { "retryNumber must be non-negative" }
        val exponential = (baseDelayMs * 2.0.pow(retryNumber.toDouble()))
            .roundToLong()
            .coerceAtMost(maxDelayMs)
        val jitter = (randomUnit().coerceIn(0.0, 1.0) * 2.0 - 1.0) * jitterRatio
        return (exponential * (1.0 + jitter)).roundToLong().coerceAtLeast(1L)
    }
}
