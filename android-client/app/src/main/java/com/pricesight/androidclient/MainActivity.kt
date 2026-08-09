package com.pricesight.androidclient

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import java.util.Date

class MainActivity : Activity() {
    private lateinit var statusView: TextView
    private val handler = Handler(Looper.getMainLooper())
    private val refreshTask = object : Runnable {
        override fun run() {
            refreshStatus()
            handler.postDelayed(this, 1000L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(32, 32, 32, 32)
        }
        val title = TextView(this).apply {
            text = getString(R.string.app_name)
            textSize = 22f
        }
        statusView = TextView(this).apply {
            textSize = 16f
            setPadding(0, 24, 0, 24)
        }
        val settingsButton = Button(this).apply {
            text = getString(R.string.open_accessibility_settings)
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }
        layout.addView(title)
        layout.addView(statusView, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        layout.addView(settingsButton)
        setContentView(layout)
    }

    override fun onResume() {
        super.onResume()
        handler.post(refreshTask)
    }

    override fun onPause() {
        handler.removeCallbacks(refreshTask)
        super.onPause()
    }

    private fun refreshStatus() {
        val state = DebugStateStore.snapshot()
        val timestamp = if (state.latestObservationTimestampMs == 0L) {
            "暂无"
        } else {
            Date(state.latestObservationTimestampMs).toString()
        }
        statusView.text = buildString {
            append("服务：")
            append(if (state.serviceEnabled) "已启用" else "未启用")
            append("\n当前包名：")
            append(state.currentPackage ?: "暂无")
            append("\n节点数：")
            append(state.nodeCount)
            append("\n最近观测：")
            append(timestamp)
        }
    }
}

