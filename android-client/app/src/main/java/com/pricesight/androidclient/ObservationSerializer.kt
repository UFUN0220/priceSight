package com.pricesight.androidclient

object ObservationSerializer {
    fun toJson(observation: AccessibilityObservation): String = buildString {
        append('{')
        appendJsonField("observation_id", observation.observationId)
        append(',')
        appendJsonNullableField("package_name", observation.packageName)
        append(',')
        appendJsonNumberField("timestamp_epoch_ms", observation.timestampEpochMs)
        append(",\"nodes\":[")
        observation.nodes.forEachIndexed { index, node ->
            if (index > 0) append(',')
            appendNode(node)
        }
        append("]}")
    }

    private fun StringBuilder.appendNode(node: ObservationNodeDto) {
        append('{')
        appendJsonField("node_id", node.nodeId)
        append(',')
        appendJsonNullableField("parent_id", node.parentId)
        append(',')
        appendJsonNullableField("class_name", node.className)
        append(',')
        appendJsonNullableField("text", node.text)
        append(',')
        appendJsonNullableField("content_description", node.contentDescription)
        append(',')
        appendJsonNullableField("resource_id", node.resourceId)
        append(',')
        appendJsonBooleanField("clickable", node.clickable)
        append(',')
        appendJsonBooleanField("scrollable", node.scrollable)
        append(',')
        appendJsonBooleanField("editable", node.editable)
        append(',')
        appendJsonBooleanField("enabled", node.enabled)
        append(',')
        appendJsonBooleanField("visible", node.visible)
        append(',')
        append("\"bounds\":")
        appendBounds(node.bounds)
        append(',')
        appendJsonNumberField("depth", node.depth)
        append(",\"children\":[")
        node.children.forEachIndexed { index, childId ->
            if (index > 0) append(',')
            appendJsonString(childId)
        }
        append("]}")
    }

    private fun StringBuilder.appendBounds(bounds: BoundsDto?) {
        if (bounds == null) {
            append("null")
            return
        }
        append('[')
        append(bounds.left)
        append(',')
        append(bounds.top)
        append(',')
        append(bounds.right)
        append(',')
        append(bounds.bottom)
        append(']')
    }

    private fun StringBuilder.appendJsonField(name: String, value: String) {
        appendJsonString(name)
        append(':')
        appendJsonString(value)
    }

    private fun StringBuilder.appendJsonNullableField(name: String, value: String?) {
        appendJsonString(name)
        append(':')
        if (value == null) append("null") else appendJsonString(value)
    }

    private fun StringBuilder.appendJsonNumberField(name: String, value: Number) {
        appendJsonString(name)
        append(':')
        append(value)
    }

    private fun StringBuilder.appendJsonBooleanField(name: String, value: Boolean) {
        appendJsonString(name)
        append(':')
        append(value)
    }

    private fun StringBuilder.appendJsonString(value: String) {
        append('"')
        value.forEach { character ->
            when (character) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                '\b' -> append("\\b")
                '\u000C' -> append("\\f")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> if (character.code < 0x20) {
                    append("\\u")
                    append(character.code.toString(16).padStart(4, '0'))
                } else {
                    append(character)
                }
            }
        }
        append('"')
    }
}
