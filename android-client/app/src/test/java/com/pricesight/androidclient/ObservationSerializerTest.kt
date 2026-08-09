package com.pricesight.androidclient

import org.junit.Assert.assertTrue
import org.junit.Test

class ObservationSerializerTest {
    @Test
    fun serializesObservationWithStableSnakeCaseFields() {
        val observation = AccessibilityObservation(
            observationId = "obs-1",
            packageName = "com.example.shop",
            timestampEpochMs = 123L,
            nodes = listOf(
                ObservationNodeDto(
                    nodeId = "1:root",
                    parentId = null,
                    className = "android.view.View",
                    text = "商品\"A",
                    contentDescription = null,
                    resourceId = "search",
                    clickable = true,
                    scrollable = false,
                    editable = false,
                    enabled = true,
                    visible = true,
                    bounds = BoundsDto(0, 1, 100, 101),
                    depth = 0,
                    children = listOf("1:root.0"),
                ),
            ),
        )

        val json = ObservationSerializer.toJson(observation)

        assertTrue(json.contains("\"observation_id\":\"obs-1\""))
        assertTrue(json.contains("\"package_name\":\"com.example.shop\""))
        assertTrue(json.contains("\"node_id\":\"1:root\""))
        assertTrue(json.contains("商品\\\"A"))
        assertTrue(json.contains("\"bounds\":{\"left\":0,\"top\":1,\"right\":100,\"bottom\":101}"))
    }
}

