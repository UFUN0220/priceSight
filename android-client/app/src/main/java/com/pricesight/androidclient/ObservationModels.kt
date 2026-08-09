package com.pricesight.androidclient

data class BoundsDto(
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int,
)

data class ObservationNodeDto(
    val nodeId: String,
    val parentId: String?,
    val className: String?,
    val text: String?,
    val contentDescription: String?,
    val resourceId: String?,
    val clickable: Boolean,
    val scrollable: Boolean,
    val editable: Boolean,
    val enabled: Boolean,
    val visible: Boolean,
    val bounds: BoundsDto?,
    val depth: Int,
    val children: List<String>,
)

data class AccessibilityObservation(
    val observationId: String,
    val packageName: String?,
    val timestampEpochMs: Long,
    val nodes: List<ObservationNodeDto>,
)

