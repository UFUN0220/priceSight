package com.pricesight.androidclient

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent

class PriceSightAccessibilityService : AccessibilityService() {
    private val collector = ObservationCollector()
    private var bridgeClient: DeviceBridgeClient? = null

    override fun onCreate() {
        super.onCreate()
        bridgeClient = DeviceBridgeClient(AndroidActionExecutor(this))
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
        bridgeClient?.submitObservationAsync(observation)
    }

    override fun onInterrupt() {
        DebugStateStore.markDisabled()
    }

    override fun onDestroy() {
        DebugStateStore.markDisabled()
        bridgeClient?.close()
        bridgeClient = null
        super.onDestroy()
    }
}
