package com.pricesight.androidclient

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent

class PriceSightAccessibilityService : AccessibilityService() {
    private val collector = ObservationCollector()
    private var exporter: ObservationHttpExporter? = null

    override fun onCreate() {
        super.onCreate()
        exporter = ObservationHttpExporter()
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        DebugStateStore.markEnabled()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        val root = runCatching { rootInActiveWindow }.getOrNull()
        val observation = collector.collect(
            root = root,
            packageName = event.packageName?.toString(),
            windowId = event.windowId,
        )
        DebugStateStore.update(observation)
        exporter?.exportAsync(observation)
    }

    override fun onInterrupt() {
        DebugStateStore.markDisabled()
    }

    override fun onDestroy() {
        DebugStateStore.markDisabled()
        exporter?.close()
        exporter = null
        super.onDestroy()
    }
}
