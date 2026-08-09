package com.pricesight.androidclient

import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/**
 * Local emulator bridge for observation upload, action polling, execution, and result reporting.
 * The backend remains responsible for planning and deterministic safety enforcement.
 */
class DeviceBridgeClient(
    private val actionExecutor: AndroidActionExecutor,
    private val baseUrl: String = DEFAULT_BASE_URL,
    private val deviceId: String = DEFAULT_DEVICE_ID,
    private val sharedToken: String = "",
    private val executor: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor(),
) {
    private val latestObservation = AtomicReference<AccessibilityObservation?>(null)
    private val uploadScheduled = AtomicBoolean(false)

    @Volatile
    private var currentObservationId: String? = null

    init {
        executor.scheduleWithFixedDelay(
            { runCatching { pollNextAction() }.onFailure(::logFailure) },
            POLL_INTERVAL_MS,
            POLL_INTERVAL_MS,
            TimeUnit.MILLISECONDS,
        )
    }

    fun submitObservationAsync(observation: AccessibilityObservation) {
        latestObservation.set(observation)
        scheduleUploadDrain()
    }

    fun close() {
        executor.shutdownNow()
    }

    private fun scheduleUploadDrain() {
        if (!uploadScheduled.compareAndSet(false, true)) return
        executor.execute {
            try {
                while (true) {
                    val observation = latestObservation.getAndSet(null) ?: break
                    runCatching { uploadObservation(observation) }.onFailure(::logFailure)
                }
            } finally {
                uploadScheduled.set(false)
                if (latestObservation.get() != null && !executor.isShutdown) {
                    scheduleUploadDrain()
                }
            }
        }
    }

    private fun uploadObservation(observation: AccessibilityObservation) {
        val encodedDeviceId = URLEncoder.encode(deviceId, Charsets.UTF_8.name())
        val response = request(
            method = "POST",
            path = "/observations?device_id=$encodedDeviceId",
            payload = ObservationSerializer.toJson(observation),
        )
        if (response.code !in 200..299) {
            error("observation upload returned HTTP ${response.code}: ${response.body}")
        }
        currentObservationId = observation.observationId
        pollNextAction()
    }

    private fun pollNextAction() {
        val observationId = currentObservationId ?: return
        val encodedDeviceId = URLEncoder.encode(deviceId, Charsets.UTF_8.name())
        val response = request("GET", "/devices/$encodedDeviceId/actions/next")
        if (response.code == HttpURLConnection.HTTP_NO_CONTENT) return
        if (response.code !in 200..299) {
            error("action poll returned HTTP ${response.code}: ${response.body}")
        }

        val command = JSONObject(response.body)
        val result = executeCommand(command, observationId)
        val report = JSONObject()
            .put("command_id", command.getString("command_id"))
            .put("result", result.toJson())
        val reportResponse = request(
            method = "POST",
            path = "/devices/$encodedDeviceId/action-results",
            payload = report.toString(),
        )
        if (reportResponse.code !in 200..299) {
            error("action result returned HTTP ${reportResponse.code}: ${reportResponse.body}")
        }
    }

    private fun executeCommand(command: JSONObject, currentId: String): BridgeActionResult {
        val action = command.getJSONObject("action")
        val actionObservationId = action.optNullableString("observation_id")
        if (actionObservationId != currentId) {
            return BridgeActionResult(
                success = false,
                status = "STALE_OBSERVATION",
                message = "command observation does not match the latest device observation",
                observationId = currentId,
            )
        }
        if (containsBlockedTerm(action.toString())) {
            return BridgeActionResult(
                success = false,
                status = "SAFETY_BLOCKED",
                message = "device safety guard rejected a high-risk action",
                observationId = currentId,
            )
        }

        val target = action.optJSONObject("target")
        val nodeId = target?.optNullableString("node_id")
        val bounds = target?.optJSONArray("bounds")?.toBounds()
        val lowLevelResult = when (action.getString("action_type")) {
            "CLICK" -> actionExecutor.click(nodeId, bounds)
            "SET_TEXT" -> actionExecutor.setText(nodeId, action.optNullableString("value").orEmpty())
            "SCROLL_FORWARD" -> actionExecutor.scroll(nodeId, true)
            "SCROLL_BACKWARD" -> actionExecutor.scroll(nodeId, false)
            "BACK" -> actionExecutor.back()
            "WAIT" -> {
                val waitMs = action.optLong("timeout_ms", 0L).coerceIn(0L, MAX_WAIT_MS)
                if (waitMs > 0) Thread.sleep(waitMs)
                AndroidActionResult(AndroidActionStatus.SUCCESS, "bounded wait completed")
            }
            "STOP" -> return BridgeActionResult(
                success = false,
                status = "SAFETY_BLOCKED",
                message = "backend requested a safety stop",
                observationId = currentId,
            )
            else -> AndroidActionResult(AndroidActionStatus.ACTION_REJECTED, "unsupported action type")
        }
        return BridgeActionResult(
            success = lowLevelResult.status == AndroidActionStatus.SUCCESS,
            status = lowLevelResult.status.name,
            message = lowLevelResult.message,
            observationId = currentId,
            matchedNodeId = nodeId,
        )
    }

    private fun request(method: String, path: String, payload: String? = null): HttpResponse {
        val connection = (URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            setRequestProperty("Accept", "application/json")
            if (sharedToken.isNotBlank()) setRequestProperty("X-Device-Token", sharedToken)
            if (payload != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
        }
        return try {
            if (payload != null) {
                connection.outputStream.use { it.write(payload.toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            HttpResponse(code, stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty())
        } finally {
            connection.disconnect()
        }
    }

    private fun logFailure(error: Throwable) {
        Log.w(TAG, "Device bridge request failed", error)
    }

    private fun containsBlockedTerm(value: String): Boolean {
        val compact = value.lowercase(Locale.ROOT).replace(Regex("[^a-z0-9\\p{L}]+"), "")
        return BLOCKED_TERMS.any { term ->
            compact.contains(term.lowercase(Locale.ROOT).replace(Regex("[^a-z0-9\\p{L}]+"), ""))
        }
    }

    private fun JSONObject.optNullableString(name: String): String? =
        if (isNull(name)) null else optString(name).takeIf { it.isNotBlank() }

    private fun JSONArray.toBounds(): BoundsDto? = if (length() == 4) {
        BoundsDto(getInt(0), getInt(1), getInt(2), getInt(3))
    } else {
        null
    }

    private data class HttpResponse(val code: Int, val body: String)

    private data class BridgeActionResult(
        val success: Boolean,
        val status: String,
        val message: String,
        val observationId: String,
        val matchedNodeId: String? = null,
    ) {
        fun toJson(): JSONObject = JSONObject()
            .put("success", success)
            .put("status", status)
            .put("message", message)
            .put("observation_id", observationId)
            .apply {
                if (matchedNodeId != null) put("matched_node_id", matchedNodeId)
            }
    }

    companion object {
        private const val TAG = "PriceSightBridge"
        private const val POLL_INTERVAL_MS = 500L
        private const val CONNECT_TIMEOUT_MS = 1500
        private const val READ_TIMEOUT_MS = 2000
        private const val MAX_WAIT_MS = 5000L
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"
        const val DEFAULT_DEVICE_ID = "android-default"
        private val BLOCKED_TERMS = listOf(
            "submit order",
            "place order",
            "confirm order",
            "payment",
            "pay now",
            "password",
            "captcha",
            "identity verification",
            "提交订单",
            "确认订单",
            "确认下单",
            "下单",
            "付款",
            "支付",
            "支付密码",
            "验证码",
            "身份验证",
        )
    }
}
