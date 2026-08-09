package com.pricesight.androidclient

import android.util.Log
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class ObservationHttpExporter(
    private val endpoint: URL = URL(DEFAULT_ENDPOINT),
    private val executor: ExecutorService = Executors.newSingleThreadExecutor(),
) {
    fun exportAsync(observation: AccessibilityObservation) {
        val payload = ObservationSerializer.toJson(observation)
        executor.execute {
            runCatching { post(payload) }
                .onFailure { error -> Log.w(TAG, "Observation export failed", error) }
        }
    }

    fun close() {
        executor.shutdownNow()
    }

    private fun post(payload: String) {
        val connection = (endpoint.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 1500
            readTimeout = 1500
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            connection.outputStream.use { output ->
                output.write(payload.toByteArray(Charsets.UTF_8))
            }
            connection.responseCode
        } finally {
            connection.disconnect()
        }
    }

    companion object {
        private const val TAG = "PriceSightExport"
        const val DEFAULT_ENDPOINT = "http://10.0.2.2:8000/observations"
    }
}

