package robot.tv

import android.app.Activity
import android.app.AlertDialog
import android.net.Uri
import android.os.Bundle
import android.text.InputType
import android.view.KeyEvent
import android.view.View
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText

/**
 * Full-screen window onto the robot's web UI. Remote keys go straight to the page.
 * Hold Back to change the robot's address.
 */
class MainActivity : Activity() {
    private lateinit var webView: WebView
    private val prefs by lazy { getSharedPreferences("robot", MODE_PRIVATE) }
    private var dialog: AlertDialog? = null

    private val robotUrl: Uri?
        get() = prefs.getString(KEY_URL, null)?.let(Uri::parse)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = RobotClient()
            isFocusable = true
            systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
        }
        setContentView(webView)
        webView.requestFocus()

        val url = robotUrl
        if (url == null) showSettings(null) else webView.loadUrl(url.toString())
    }

    override fun onResume() {
        super.onResume()
        webView.onResume()
    }

    override fun onPause() {
        webView.onPause()
        super.onPause()
    }

    override fun onDestroy() {
        dialog?.dismiss()
        webView.destroy()
        super.onDestroy()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            event.startTracking()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onKeyLongPress(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            showSettings(null)
            return true
        }
        return super.onKeyLongPress(keyCode, event)
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && event.isTracking && !event.isCanceled) {
            // The page decides what Back means; it returns false on its home screen.
            webView.evaluateJavascript("window.robotBack ? window.robotBack() : false") { handled ->
                if (handled != "true") finish()
            }
            return true
        }
        return super.onKeyUp(keyCode, event)
    }

    private fun showSettings(message: String?) {
        if (dialog?.isShowing == true) return
        val input = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            hint = getString(R.string.settings_hint)
            setText(prefs.getString(KEY_URL, ""))
        }
        val builder = AlertDialog.Builder(this)
            .setTitle(R.string.settings_title)
            .setView(input)
            .setPositiveButton(R.string.settings_save) { _, _ ->
                val url = normalize(input.text.toString())
                if (url == null) {
                    showSettings(getString(R.string.settings_empty))
                } else {
                    prefs.edit().putString(KEY_URL, url).apply()
                    webView.loadUrl(url)
                }
            }
            .setOnCancelListener { if (robotUrl == null) finish() }
        if (message != null) builder.setMessage(message)
        if (robotUrl != null) {
            builder.setNeutralButton(R.string.settings_retry) { _, _ -> webView.reload() }
        }
        dialog = builder.show()
    }

    private fun normalize(raw: String): String? {
        val trimmed = raw.trim().trimEnd('/')
        if (trimmed.isEmpty()) return null
        return if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) trimmed else "http://$trimmed"
    }

    private inner class RobotClient : WebViewClient() {
        // Stay on the robot's address.
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val robot = robotUrl ?: return true
            val url = request.url
            return url.scheme != robot.scheme || url.host != robot.host || url.port != robot.port
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (request.isForMainFrame) showSettings(getString(R.string.load_failed))
        }
    }

    private companion object {
        const val KEY_URL = "url"
    }
}
