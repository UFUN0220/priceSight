package com.pricesight.androidclient

import android.accessibilityservice.AccessibilityService
import android.util.Log
import android.view.accessibility.AccessibilityEvent

class PriceSightAccessibilityService : AccessibilityService() {
    private val collector = ObservationCollector()
    private var bridgeClient: DeviceBridgeClient? = null

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "SERVICE_CREATED device_id=${DeviceBridgeClient.DEFAULT_DEVICE_ID}")
        bridgeClient = DeviceBridgeClient(AndroidActionExecutor(this))
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        DebugStateStore.markEnabled()
        Log.i(TAG, "SERVICE_CONNECTED device_id=${DeviceBridgeClient.DEFAULT_DEVICE_ID}")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        val packageName = event.packageName?.toString()
        try {
            val root = runCatching { rootInActiveWindow }.getOrNull()
            Log.d(TAG, "OBSERVATION_START device_id=${DeviceBridgeClient.DEFAULT_DEVICE_ID} root_exists=${root != null} package=$packageName")
            val observation = collector.collect(
                root = root,
                packageName = packageName,
                windowId = event.windowId,
            )
            DebugStateStore.update(observation)
            bridgeClient?.submitObservationAsync(observation)
            Log.i(TAG, "OBSERVATION_SUCCESS device_id=${DeviceBridgeClient.DEFAULT_DEVICE_ID} observation_id=${observation.observationId} node_count=${observation.nodes.size}")
        } catch (error: RuntimeException) {
            Log.e(
                TAG,
                "OBSERVATION_FAILED device_id=${DeviceBridgeClient.DEFAULT_DEVICE_ID} package=$packageName error_type=${error::class.java.simpleName}",
                error,
            )
        }
    }

    override fun onInterrupt() {
        DebugStateStore.markDisabled()
        Log.w(TAG, "SERVICE_INTERRUPTED device_id=${DeviceBridgeClient.DEFAULT_DEVICE_ID}")
    }

    override fun onDestroy() {
        Log.i(TAG, "SERVICE_DESTROYED device_id=${DeviceBridgeClient.DEFAULT_DEVICE_ID}")
        DebugStateStore.markDisabled()
        bridgeClient?.close()
        bridgeClient = null
        super.onDestroy()
    }

    companion object {
        private const val TAG = "PriceSightRuntime"
    }
}
