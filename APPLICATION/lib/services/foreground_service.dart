import 'dart:async';
import 'dart:isolate';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:flutter_foreground_task/models/notification_icon.dart';
import 'package:flutter_foreground_task/models/service_request_result.dart';
import 'health_service.dart';
import 'data_logger.dart';

/// Handler for the foreground service that collects health data in the background
@pragma('vm:entry-point')
void startCallback() {
  FlutterForegroundTask.setTaskHandler(HealthDataTaskHandler());
}

class HealthDataTaskHandler extends TaskHandler {
  SendPort? _sendPort;
  Timer? _timer;
  int _sampleCount = 0;

  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {
    print('Health data collection service started');

    // Start periodic data collection (every 5 minutes)
    _timer = Timer.periodic(const Duration(minutes: 5), (timer) async {
      await _collectHealthData();
    });

    // Also collect data immediately on start
    await _collectHealthData();
  }

  @override
  void onRepeatEvent(DateTime timestamp) {
    // This is called based on the interval set in ForegroundTaskOptions
    // We're using Timer instead, but this could be used as an alternative
  }

  @override
  Future<void> onDestroy(DateTime timestamp) async {
    print('Health data collection service stopped');
    _timer?.cancel();

    // Flush any remaining data
    await DataLogger().flush();
  }

  @override
  void onNotificationButtonPressed(String id) {
    print('Notification button pressed: $id');
  }

  @override
  void onNotificationPressed() {
    print('Notification pressed');
    FlutterForegroundTask.launchApp('/');
  }

  Future<void> _collectHealthData() async {
    try {
      final healthService = HealthService();
      final hasPermissions = await healthService.hasPermissions();
      if (!hasPermissions) return;
      final dataLogger = DataLogger();

      // Fetch data from the last 5 minutes
      final now = DateTime.now();
      final startTime = now.subtract(const Duration(minutes: 5));

      final dataPoints = await healthService.fetchHealthData(
        startTime: startTime,
        endTime: now,
      );

      if (dataPoints.isNotEmpty) {
        await dataLogger.logDataPoints(dataPoints);
        _sampleCount += dataPoints.length;

        print(
            'Collected ${dataPoints.length} health data points. Total: $_sampleCount');

        // Update notification with current stats
        await _updateNotification();
      }
    } catch (e) {
      print('Error collecting health data: $e');
    }
  }

  Future<void> _updateNotification() async {
    try {
      final healthService = HealthService();
      final heartRate = await healthService.getLatestHeartRate();

      final hrText = heartRate != null ? '${heartRate.toInt()} bpm' : 'N/A';

      FlutterForegroundTask.updateService(
        notificationTitle: 'Health Data Collection Active',
        notificationText: 'HR: $hrText | Samples: $_sampleCount',
      );
    } catch (e) {
      print('Error updating notification: $e');
    }
  }
}

/// Service for managing the foreground task
class ForegroundService {
  static final ForegroundService _instance = ForegroundService._internal();
  factory ForegroundService() => _instance;
  ForegroundService._internal();

  bool _isRunning = false;

  /// Initialize the foreground task
  Future<void> initialize() async {
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'health_data_collection',
        channelName: 'Health Data Collection',
        channelDescription: 'Collects health data from your wearable device',
        channelImportance: NotificationChannelImportance.LOW,
        priority: NotificationPriority.LOW,
      ),
      iosNotificationOptions: const IOSNotificationOptions(
        showNotification: true,
        playSound: false,
      ),
      foregroundTaskOptions: ForegroundTaskOptions(
        eventAction: ForegroundTaskEventAction.repeat(5000),
        autoRunOnBoot: false,
        autoRunOnMyPackageReplaced: false,
        allowWakeLock: true,
        allowWifiLock: false,
      ),
    );
  }

  /// Start the foreground service
  Future<bool> startService() async {
    if (_isRunning) {
      print('Service already running');
      return true;
    }

    // Request permissions for the foreground service
    if (!await FlutterForegroundTask.isIgnoringBatteryOptimizations) {
      await FlutterForegroundTask.requestIgnoreBatteryOptimization();
    }

    // Check if notification permission is granted (Android 13+)
    final notificationPermission =
        await FlutterForegroundTask.checkNotificationPermission();
    if (notificationPermission != NotificationPermission.granted) {
      await FlutterForegroundTask.requestNotificationPermission();
    }

    final result = await FlutterForegroundTask.startService(
      serviceId: 256,
      notificationTitle: 'Health Data Collection Active',
      notificationText: 'Collecting data from your wearable device',
      notificationIcon: const NotificationIcon(
        metaDataName: 'com.healthml.health_data_collector.notification_icon',
      ),
      callback: startCallback,
    );

    final success = result is ServiceRequestSuccess;
    _isRunning = success;
    return success;
  }

  /// Stop the foreground service
  Future<bool> stopService() async {
    if (!_isRunning) {
      print('Service not running');
      return true;
    }

    final result = await FlutterForegroundTask.stopService();
    final success = result is ServiceRequestSuccess;
    _isRunning = !success;
    return success;
  }

  /// Check if the service is running
  bool isRunning() => _isRunning;

  /// Update service running status
  Future<void> updateRunningStatus() async {
    _isRunning = await FlutterForegroundTask.isRunningService;
  }
}
