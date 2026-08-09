package com.pricesight.androidclient

import android.provider.Settings
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

/**
 * Real-device/emulator harness for the complete observation -> action -> callback loop.
 * It intentionally fails with BLOCKED when the accessibility service or backend is not provisioned.
 */
@RunWith(AndroidJUnit4::class)
class DeviceBridgeRuntimeInstrumentedTest {
    @Test
    fun testObservationUploadBackPollExecutionCallback() {
        assertTrue(
            "BLOCKED: PriceSightAccessibilityService is not enabled",
            isAccessibilityServiceEnabled(),
        )
        val initial = awaitSnapshot { it.has("latest_observation_id") && !it.isNull("latest_observation_id") }
        val observationId = initial.getString("latest_observation_id")
        val initialCompleted = initial.optInt("completed_action_count", 0)
        val actionId = UUID.randomUUID().toString()
        postAction(
            JSONObject()
                .put("action_id", actionId)
                .put("action_type", "BACK")
                .put("observation_id", observationId)
                .put("timeout_ms", 3000),
        )
        val completed = awaitSnapshot { it.optInt("completed_action_count", 0) > initialCompleted }
        assertTrue("action lifecycle must report a terminal success or failure", completed.has("lifecycle_counts"))
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val enabled = InstrumentationRegistry.getInstrumentation().targetContext.contentResolver
            .let { Settings.Secure.getString(it, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES).orEmpty() }
        return enabled.contains("com.pricesight.androidclient/com.pricesight.androidclient.PriceSightAccessibilityService")
    }

    private fun awaitSnapshot(predicate: (JSONObject) -> Boolean): JSONObject {
        repeat(20) {
            val response = request("GET", "/devices/android-default")
            if (response.code in 200..299 && predicate(response.body)) return response.body
            Thread.sleep(500)
        }
        fail("BLOCKED: backend/device observation was not available at $BASE_URL")
        error("unreachable")
    }

    private fun postAction(action: JSONObject) {
        val response = request("POST", "/devices/android-default/actions", action)
        assertTrue("backend action enqueue failed: ${response.body}", response.code in 200..299)
    }

    private fun request(method: String, path: String, payload: JSONObject? = null): HttpResponse {
        val connection = (URL(BASE_URL + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 1500
            readTimeout = 2000
            setRequestProperty("Content-Type", "application/json")
            if (payload != null) doOutput = true
        }
        return try {
            payload?.let { connection.outputStream.use { stream -> stream.write(it.toString().toByteArray()) } }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            HttpResponse(code, JSONObject(body))
        } finally {
            connection.disconnect()
        }
    }

    private data class HttpResponse(val code: Int, val body: JSONObject)

    companion object {
        private const val BASE_URL = "http://10.0.2.2:8000"
    }
}
