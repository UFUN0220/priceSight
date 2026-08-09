package com.pricesight.androidclient

data class DebugState(
    val serviceEnabled: Boolean,
    val currentPackage: String?,
    val nodeCount: Int,
    val latestObservationTimestampMs: Long,
)

object DebugStateStore {
    @Volatile
    private var state = DebugState(false, null, 0, 0L)

    fun snapshot(): DebugState = state

    fun update(observation: AccessibilityObservation) {
        state = DebugState(
            serviceEnabled = true,
            currentPackage = observation.packageName,
            nodeCount = observation.nodes.size,
            latestObservationTimestampMs = observation.timestampEpochMs,
        )
    }

    fun markEnabled() {
        state = state.copy(serviceEnabled = true)
    }

    fun markDisabled() {
        state = state.copy(serviceEnabled = false)
    }
}
