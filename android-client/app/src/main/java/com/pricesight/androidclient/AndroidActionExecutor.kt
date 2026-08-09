package com.pricesight.androidclient

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo

enum class AndroidActionStatus {
    SUCCESS,
    TARGET_NOT_FOUND,
    ACTION_REJECTED,
}

data class AndroidActionResult(
    val status: AndroidActionStatus,
    val message: String,
)

class AndroidActionExecutor(
    private val service: AccessibilityService,
    private val rootProvider: () -> AccessibilityNodeInfo? = { service.rootInActiveWindow },
) {
    fun click(nodeId: String?, freshBounds: BoundsDto?): AndroidActionResult {
        val node = resolveFreshNode(nodeId)
        if (node != null && runCatching { node.performAction(AccessibilityNodeInfo.ACTION_CLICK) }.getOrDefault(false)) {
            return AndroidActionResult(AndroidActionStatus.SUCCESS, "node click performed")
        }
        if (freshBounds != null) {
            return gestureClick(freshBounds)
        }
        return AndroidActionResult(AndroidActionStatus.TARGET_NOT_FOUND, "fresh node and bounds were unavailable")
    }

    fun setText(nodeId: String?, value: String): AndroidActionResult {
        val node = resolveFreshNode(nodeId)
            ?: return AndroidActionResult(AndroidActionStatus.TARGET_NOT_FOUND, "fresh node was unavailable")
        val arguments = Bundle().apply {
            putCharSequence(
                AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                value,
            )
        }
        val accepted = runCatching {
            node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)
        }.getOrDefault(false)
        return if (accepted) {
            AndroidActionResult(AndroidActionStatus.SUCCESS, "text set action performed")
        } else {
            AndroidActionResult(AndroidActionStatus.ACTION_REJECTED, "node rejected set text")
        }
    }

    fun scroll(nodeId: String?, forward: Boolean): AndroidActionResult {
        val node = resolveFreshNode(nodeId) ?: rootProvider()
        if (node == null) {
            return AndroidActionResult(AndroidActionStatus.TARGET_NOT_FOUND, "fresh scroll node was unavailable")
        }
        val action = if (forward) {
            AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        } else {
            AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        }
        val accepted = runCatching { node.performAction(action) }.getOrDefault(false)
        return if (accepted) {
            AndroidActionResult(AndroidActionStatus.SUCCESS, "scroll action performed")
        } else {
            AndroidActionResult(AndroidActionStatus.ACTION_REJECTED, "node rejected scroll")
        }
    }

    fun back(): AndroidActionResult {
        val accepted = service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
        return if (accepted) {
            AndroidActionResult(AndroidActionStatus.SUCCESS, "global back performed")
        } else {
            AndroidActionResult(AndroidActionStatus.ACTION_REJECTED, "global back rejected")
        }
    }

    private fun gestureClick(bounds: BoundsDto): AndroidActionResult {
        val path = Path().apply {
            moveTo((bounds.left + bounds.right) / 2f, (bounds.top + bounds.bottom) / 2f)
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0L, 60L))
            .build()
        val dispatched = service.dispatchGesture(gesture, null, null)
        return if (dispatched) {
            AndroidActionResult(AndroidActionStatus.SUCCESS, "fresh-bounds gesture dispatched")
        } else {
            AndroidActionResult(AndroidActionStatus.ACTION_REJECTED, "gesture dispatch rejected")
        }
    }

    private fun resolveFreshNode(nodeId: String?): AccessibilityNodeInfo? {
        if (nodeId.isNullOrBlank()) return null
        val path = nodeId.substringAfter(':', missingDelimiterValue = nodeId)
        if (path == "root") return rootProvider()
        if (!path.startsWith("root.")) return null
        var current = rootProvider() ?: return null
        path.removePrefix("root.").split('.').forEach { indexText ->
            val index = indexText.toIntOrNull() ?: return null
            current = runCatching { current.getChild(index) }.getOrNull() ?: return null
        }
        return current
    }
}

