package com.pricesight.androidclient

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo

class ObservationCollector(
    private val clock: () -> Long = { System.currentTimeMillis() },
) {
    fun collect(
        root: AccessibilityNodeInfo?,
        packageName: String?,
        windowId: Int,
    ): AccessibilityObservation {
        val nodes = mutableListOf<ObservationNodeDto>()
        if (root != null) {
            visit(root, null, "root", 0, windowId, nodes)
        }
        val timestamp = clock()
        return AccessibilityObservation(
            observationId = "$windowId-$timestamp",
            packageName = packageName,
            timestampEpochMs = timestamp,
            nodes = nodes,
        )
    }

    private fun visit(
        node: AccessibilityNodeInfo,
        parentId: String?,
        path: String,
        depth: Int,
        windowId: Int,
        output: MutableList<ObservationNodeDto>,
    ) {
        val nodeId = "$windowId:$path"
        val childNodes = mutableListOf<Pair<String, AccessibilityNodeInfo>>()
        val childCount = safe(default = 0) { node.childCount }
        for (index in 0 until childCount) {
            val child = safe<AccessibilityNodeInfo?>(default = null) { node.getChild(index) }
            if (child != null) {
                childNodes += "$windowId:$path.$index" to child
            }
        }

        val bounds = Rect()
        val hasBounds = safe(default = false) {
            node.getBoundsInScreen(bounds)
            true
        }
        output += ObservationNodeDto(
            nodeId = nodeId,
            parentId = parentId,
            className = safe(default = null) { node.className?.toString() },
            text = safe(default = null) { node.text?.toString() },
            contentDescription = safe(default = null) { node.contentDescription?.toString() },
            resourceId = safe(default = null) { node.viewIdResourceName },
            clickable = safe(default = false) { node.isClickable },
            scrollable = safe(default = false) { node.isScrollable },
            editable = safe(default = false) { node.isEditable },
            enabled = safe(default = false) { node.isEnabled },
            visible = safe(default = false) { node.isVisibleToUser },
            bounds = if (hasBounds) BoundsDto(bounds.left, bounds.top, bounds.right, bounds.bottom) else null,
            depth = depth,
            children = childNodes.map { it.first },
        )

        childNodes.forEachIndexed { index, child ->
            visit(child.second, nodeId, "$path.$index", depth + 1, windowId, output)
        }
    }

    private fun <T> safe(default: T, block: () -> T): T = try {
        block()
    } catch (_: RuntimeException) {
        default
    }
}
