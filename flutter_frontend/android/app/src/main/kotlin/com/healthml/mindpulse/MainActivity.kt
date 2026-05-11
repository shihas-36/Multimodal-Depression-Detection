package com.healthml.mindpulse

import android.content.ActivityNotFoundException
import android.os.Build
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import android.content.Intent
import android.net.Uri

class MainActivity: FlutterFragmentActivity() {
    private val CHANNEL = "com.healthml.mindpulse/permissions"
    private val FUSION_CHANNEL = "fusion_trainer"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // ── Existing: Health Connect permissions channel ──────────────────────
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "getHealthConnectAvailability" -> {
                        result.success(getHealthConnectAvailability())
                    }
                    "launchHealthConnectPermissions" -> {
                        val launched = launchHealthConnectPermissions()
                        if (launched) {
                            result.success(true)
                        } else {
                            result.error(
                                "HEALTH_CONNECT_UNAVAILABLE",
                                "Unable to open Health Connect settings or install page",
                                null
                            )
                        }
                    }
                    else -> result.notImplemented()
                }
            }

        // ── New: PyTorch Fusion Trainer channel ───────────────────────────────
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, FUSION_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "trainFusionModel" -> {
                        try {
                            val textEmbedding =
                                call.argument<List<Double>>("textEmbedding")
                            val wearableEmbedding =
                                call.argument<List<Double>>("wearableEmbedding")
                            val label =
                                call.argument<Int>("label")

                            val trainer = FusionTrainer.getInstance(applicationContext)
                            val output = trainer.train(
                                textEmbedding!!,
                                wearableEmbedding!!,
                                label!!
                            )
                            result.success(output)
                        } catch (e: Exception) {
                            result.error("TRAIN_ERROR", e.message, null)
                        }
                    }
                    "getLatestWeights" -> {
                        try {
                            val trainer = FusionTrainer.getInstance(applicationContext)
                            val weights = trainer.getLatestWeights()
                            result.success(weights)
                        } catch (e: Exception) {
                            result.error("WEIGHT_EXTRACTION_ERROR", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun getHealthConnectAvailability(): String {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) {
            return "not_supported"
        }

        val packageName = "com.google.android.apps.healthdata"
        val installed = try {
            packageManager.getPackageInfo(packageName, 0)
            true
        } catch (e: Exception) {
            false
        }

        return if (installed) "available" else "not_installed"
    }

    private fun launchHealthConnectPermissions(): Boolean {
        val settingsIntent = Intent("androidx.health.ACTION_HEALTH_CONNECT_SETTINGS").apply {
            setPackage("com.google.android.apps.healthdata")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        if (startIfResolvable(settingsIntent)) return true

        val appLaunchIntent = packageManager
            .getLaunchIntentForPackage("com.google.android.apps.healthdata")
            ?.apply { addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) }
        if (appLaunchIntent != null && startIfResolvable(appLaunchIntent)) return true

        val playStoreIntent = Intent(
            Intent.ACTION_VIEW,
            Uri.parse("market://details?id=com.google.android.apps.healthdata")
        ).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        if (startIfResolvable(playStoreIntent)) return true

        val webStoreIntent = Intent(
            Intent.ACTION_VIEW,
            Uri.parse("https://play.google.com/store/apps/details?id=com.google.android.apps.healthdata")
        ).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        return startIfResolvable(webStoreIntent)
    }

    private fun startIfResolvable(intent: Intent): Boolean {
        return try {
            val canResolve = intent.resolveActivity(packageManager) != null
            if (!canResolve) return false
            startActivity(intent)
            true
        } catch (e: ActivityNotFoundException) {
            false
        } catch (e: Exception) {
            android.util.Log.e("MainActivity", "Failed to open intent: ${e.message}")
            false
        }
    }

}
