package com.pricesight.androidclient

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ObservationCollectorTest {
    @Test
    fun nullRootProducesSafeEmptyObservation() {
        val observation = ObservationCollector { 42L }.collect(null, "com.example.shop", 7)

        assertEquals("7-42", observation.observationId)
        assertEquals("com.example.shop", observation.packageName)
        assertEquals(42L, observation.timestampEpochMs)
        assertEquals(0, observation.nodes.size)
        assertNull(observation.nodes.firstOrNull())
    }
}

