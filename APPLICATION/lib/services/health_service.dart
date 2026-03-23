import 'package:health/health.dart';
import 'package:permission_handler/permission_handler.dart';
import '../models/health_data_point.dart' as models;

/// Service for interacting with Health Connect and collecting health data
class HealthService {
  static final HealthService _instance = HealthService._internal();
  factory HealthService() => _instance;
  HealthService._internal();

  final Health _health = Health();

  // Source keywords typically associated with wearable ecosystems.
  static const List<String> _preferredWearableSourceKeywords = [
    'samsung',
    'shealth',
    'watch',
    'wear',
    'fitbit',
    'garmin',
    'polar',
    'amazfit',
    'zepp',
    'huawei',
    'whoop',
    'oura',
  ];

  /// Health data types to collect
  static const List<HealthDataType> _dataTypes = [
    HealthDataType.STEPS,
    HealthDataType.HEART_RATE,
    HealthDataType.TOTAL_CALORIES_BURNED,
    HealthDataType.SLEEP_SESSION,
    HealthDataType.HEART_RATE_VARIABILITY_RMSSD,
  ];

  // Additional types used for vendor-specific fallback reads.
  static const List<HealthDataType> _heartRateFallbackTypes = [
    HealthDataType.HEART_RATE,
    HealthDataType.RESTING_HEART_RATE,
    HealthDataType.WALKING_HEART_RATE,
  ];

  static const List<HealthDataType> _calorieFallbackTypes = [
    HealthDataType.TOTAL_CALORIES_BURNED,
    HealthDataType.ACTIVE_ENERGY_BURNED,
    HealthDataType.BASAL_ENERGY_BURNED,
  ];

  /// Check if all required permissions are granted.
  /// Uses Health Connect's own permission API — does NOT do a data read.
  /// Health Connect returns null when it cannot determine status — treat that
  /// as granted so the app is not permanently blocked on valid devices.
  Future<bool> hasPermissions() async {
    try {
      final sensorsGranted = await Permission.sensors.isGranted;
      if (!sensorsGranted) return false;

      final permissions = _dataTypes.map((_) => HealthDataAccess.READ).toList();
      final granted =
          await _health.hasPermissions(_dataTypes, permissions: permissions);
      // granted == true  → all granted
      // granted == null  → undetermined (treat as granted to avoid false blocks)
      // granted == false → explicitly denied
      return granted != false;
    } catch (e) {
      return false;
    }
  }

  /// Returns permission and per-metric read diagnostics for troubleshooting.
  Future<Map<String, String>> getReadDiagnostics() async {
    final now = DateTime.now();
    final diagnostics = <String, String>{};

    final sensorsGranted = await Permission.sensors.isGranted;
    diagnostics['Sensors permission'] = sensorsGranted ? 'granted' : 'denied';

    try {
      final permissions = _dataTypes.map((_) => HealthDataAccess.READ).toList();
      final granted =
          await _health.hasPermissions(_dataTypes, permissions: permissions);
      diagnostics['Health Connect permission'] =
          granted == true ? 'granted' : 'denied';
    } catch (_) {
      diagnostics['Health Connect permission'] = 'error';
    }

    diagnostics['Steps'] = await _probeReadStatus(
      HealthDataType.STEPS,
      DateTime(now.year, now.month, now.day),
      now,
    );
    diagnostics['Sleep'] = await _probeReadStatus(
      HealthDataType.SLEEP_SESSION,
      now.subtract(const Duration(days: 1)),
      now,
    );
    diagnostics['Calories'] = await _probeMultiReadStatus(
      _calorieFallbackTypes,
      DateTime(now.year, now.month, now.day),
      now,
    );
    diagnostics['Heart Rate'] = await _probeReadStatus(
      HealthDataType.HEART_RATE,
      now.subtract(const Duration(hours: 24)),
      now,
    );
    diagnostics['HRV'] = await _probeReadStatus(
      HealthDataType.HEART_RATE_VARIABILITY_RMSSD,
      now.subtract(const Duration(hours: 24)),
      now,
    );

    return diagnostics;
  }

  Future<String> _probeReadStatus(
    HealthDataType type,
    DateTime startTime,
    DateTime endTime,
  ) async {
    try {
      final data = await _health.getHealthDataFromTypes(
        types: [type],
        startTime: startTime,
        endTime: endTime,
      );
      if (data.isEmpty) return 'no_data';
      return 'ok (${data.length})';
    } catch (e) {
      final error = e.toString().toLowerCase();
      if (error.contains('securityexception') ||
          error.contains('doesn\'t have android.permission.health')) {
        return 'denied';
      }
      return 'error';
    }
  }

  Future<String> _probeMultiReadStatus(
    List<HealthDataType> types,
    DateTime startTime,
    DateTime endTime,
  ) async {
    for (final type in types) {
      final status = await _probeReadStatus(type, startTime, endTime);
      if (status.startsWith('ok')) return status;
    }
    return 'no_data';
  }

  Future<List<HealthDataPoint>> _readDataByTypesBestEffort({
    required List<HealthDataType> types,
    required DateTime startTime,
    required DateTime endTime,
  }) async {
    final allData = <HealthDataPoint>[];

    for (final type in types) {
      try {
        final data = await _health.getHealthDataFromTypes(
          types: [type],
          startTime: startTime,
          endTime: endTime,
        );
        allData.addAll(data);
      } catch (_) {
        // Optional fallback types may be unavailable or not authorized.
      }
    }

    return allData;
  }

  /// Request all required permissions
  Future<bool> requestPermissions() async {
    try {
      // Request body sensors permission
      final bodySensorsStatus = await Permission.sensors.request();
      if (!bodySensorsStatus.isGranted) {
        print('Body sensors permission denied');
        return false;
      }

      // Request Health Connect permissions
      final permissions = _dataTypes.map((type) {
        return HealthDataAccess.READ;
      }).toList();

      final authorized = await _health.requestAuthorization(
        _dataTypes,
        permissions: permissions,
      );

      return authorized;
    } catch (e) {
      print('Error requesting permissions: $e');
      return false;
    }
  }

  /// Fetch health data for a given time range
  Future<List<models.HealthDataPoint>> fetchHealthData({
    required DateTime startTime,
    required DateTime endTime,
  }) async {
    // Relaxed check: Try to fetch data even if the strict check fails,
    // because permissions might be granted but not detected correctly.
    /*
    if (!_isAuthorized) {
      final hasPerms = await hasPermissions();
      if (!hasPerms) {
        throw Exception('Health permissions not granted');
      }
      _isAuthorized = true;
    }
    */

    try {
      final healthData = await _health.getHealthDataFromTypes(
        types: _dataTypes,
        startTime: startTime,
        endTime: endTime,
      );

      // Convert Health package data points to our custom model
      final dataPoints = healthData.map((point) {
        return models.HealthDataPoint(
          timestamp: point.dateFrom,
          dataType: point.type.name,
          value: _extractValue(point),
          unit: point.unitString,
          source: point.sourceName,
        );
      }).toList();

      return dataPoints;
    } catch (e) {
      print('Error fetching health data: $e');
      return [];
    }
  }

  /// Extract value from HealthDataPoint based on type
  dynamic _extractValue(HealthDataPoint point) {
    if (point.value is NumericHealthValue) {
      return (point.value as NumericHealthValue).numericValue;
    } else if (point.value is WorkoutHealthValue) {
      return (point.value as WorkoutHealthValue).totalEnergyBurned ?? 0;
    } else {
      return point.value.toString();
    }
  }

  /// Get the latest heart rate reading
  Future<double?> getLatestHeartRate() async {
    try {
      final now = DateTime.now();
      final lookback = now.subtract(const Duration(hours: 24));
      final data = await _readDataByTypesBestEffort(
        types: _heartRateFallbackTypes,
        startTime: lookback,
        endTime: now,
      );

      if (data.isEmpty) {
        _logSourceSelection('HEART_RATE', const [], const []);
        return null;
      }

      final selected = _selectPreferredSourceData(data);
      final pool = selected.isNotEmpty ? selected : data;
      _logSourceSelection('HEART_RATE', data, selected);

      // Get the most recent reading
      final latest =
          pool.reduce((a, b) => a.dateFrom.isAfter(b.dateFrom) ? a : b);

      return _extractValue(latest) as double?;
    } catch (e) {
      print('Error getting latest heart rate: $e');
      return null;
    }
  }

  /// Get today's step count
  Future<int?> getTodaySteps() async {
    try {
      final now = DateTime.now();
      final startOfDay = DateTime(now.year, now.month, now.day);

      final data = await _health.getHealthDataFromTypes(
        types: [HealthDataType.STEPS],
        startTime: startOfDay,
        endTime: now,
      );

      final preferred = _selectPreferredSourceData(data);
      if (preferred.isNotEmpty) {
        _logSourceSelection('STEPS', data, preferred);
        // Use wearable-origin records when available to avoid phone-source drift.
        return _sumNumeric(preferred).toInt();
      }

      _logSourceSelection('STEPS', data, const []);

      // Fallback to Health Connect aggregate when no wearable-tagged source exists.
      // Aggregate respects Health Connect's source-priority rules better than naive sums.
      final aggregated =
          await _health.getTotalStepsInInterval(startOfDay, now, includeManualEntry: false);
      if (aggregated != null) return aggregated;

      if (data.isEmpty) return null;
      return _sumNumeric(data).toInt();
    } catch (e) {
      print('Error getting today\'s steps: $e');
      return null;
    }
  }

  /// Get today's active calories burned
  Future<double?> getTodayCalories() async {
    try {
      final now = DateTime.now();
      final startOfDay = DateTime(now.year, now.month, now.day);

      final data = await _readDataByTypesBestEffort(
        types: _calorieFallbackTypes,
        startTime: startOfDay,
        endTime: now,
      );

      if (data.isEmpty) {
        _logSourceSelection('CALORIES', const [], const []);
        return null;
      }

      final selected = _selectPreferredSourceData(data);
      final pool = selected.isNotEmpty ? selected : data;
      _logSourceSelection('CALORIES', data, selected);

      final totalCalories =
          _sumForType(pool, HealthDataType.TOTAL_CALORIES_BURNED);
      if (totalCalories > 0) {
        return totalCalories;
      }

      final activeCalories =
          _sumForType(pool, HealthDataType.ACTIVE_ENERGY_BURNED);
      final basalCalories =
          _sumForType(pool, HealthDataType.BASAL_ENERGY_BURNED);
      final combined = activeCalories + basalCalories;
      if (combined > 0) {
        return combined;
      }

      return _sumNumeric(pool);
    } catch (e) {
      print('Error getting today\'s calories: $e');
      return null;
    }
  }

  /// Get HRV RMSSD data
  Future<double?> getLatestHRV() async {
    try {
      final now = DateTime.now();
      final data = await _health.getHealthDataFromTypes(
        types: [HealthDataType.HEART_RATE_VARIABILITY_RMSSD],
        startTime: now.subtract(const Duration(hours: 24)),
        endTime: now,
      );

      if (data.isEmpty) {
        _logSourceSelection('HEART_RATE_VARIABILITY_RMSSD', const [], const []);
        return null;
      }

      final selected = _selectPreferredSourceData(data);
      final pool = selected.isNotEmpty ? selected : data;
      _logSourceSelection('HEART_RATE_VARIABILITY_RMSSD', data, selected);

      // Get the most recent reading
      final latest =
          pool.reduce((a, b) => a.dateFrom.isAfter(b.dateFrom) ? a : b);

      return _extractValue(latest) as double?;
    } catch (e) {
      print('Error getting HRV: $e');
      return null;
    }
  }

  /// Get sleep data for last night
  Future<int?> getLastNightSleep() async {
    try {
      final now = DateTime.now();
      final yesterday = now.subtract(const Duration(days: 1));

      final data = await _health.getHealthDataFromTypes(
        types: [HealthDataType.SLEEP_SESSION],
        startTime: yesterday,
        endTime: now,
      );

      if (data.isEmpty) {
        _logSourceSelection('SLEEP_SESSION', const [], const []);
        return null;
      }

      final selected = _selectPreferredSourceData(data);
      final pool = selected.isNotEmpty ? selected : data;
      _logSourceSelection('SLEEP_SESSION', data, selected);

      // Calculate total sleep duration in minutes
      int totalMinutes = 0;
      for (final point in pool) {
        final duration = point.dateTo.difference(point.dateFrom);
        totalMinutes += duration.inMinutes;
      }

      return totalMinutes;
    } catch (e) {
      print('Error getting sleep data: $e');
      return null;
    }
  }

  List<HealthDataPoint> _selectPreferredSourceData(List<HealthDataPoint> data) {
    if (data.isEmpty) return const [];
    final preferred = data.where(_isPreferredWearableSource).toList();
    return preferred;
  }

  bool _isPreferredWearableSource(HealthDataPoint point) {
    final source = '${point.sourceId} ${point.sourceName}'.toLowerCase();
    return _preferredWearableSourceKeywords.any(source.contains);
  }

  double _sumNumeric(List<HealthDataPoint> data) {
    double total = 0;
    for (final point in data) {
      final value = _extractValue(point);
      if (value is num) {
        total += value.toDouble();
      }
    }
    return total;
  }

  double _sumForType(List<HealthDataPoint> data, HealthDataType type) {
    return _sumNumeric(data.where((point) => point.type == type).toList());
  }

  void _logSourceSelection(
    String metric,
    List<HealthDataPoint> allData,
    List<HealthDataPoint> preferredData,
  ) {
    if (allData.isEmpty) {
      print('I/FLUTTER_HEALTH_SOURCE: $metric has no records');
      return;
    }

    final countsBySource = <String, int>{};
    for (final point in allData) {
      final sourceKey = '${point.sourceName} (${point.sourceId})';
      countsBySource[sourceKey] = (countsBySource[sourceKey] ?? 0) + 1;
    }

    final summary = countsBySource.entries
        .map((entry) => '${entry.key}: ${entry.value}')
        .join(', ');

    if (preferredData.isEmpty) {
      print('I/FLUTTER_HEALTH_SOURCE: $metric using aggregate/all sources. '
          'available=[$summary]');
      return;
    }

    final selectedSources = preferredData
        .map((point) => '${point.sourceName} (${point.sourceId})')
        .toSet()
        .join(', ');
    print('I/FLUTTER_HEALTH_SOURCE: $metric using wearable-priority sources '
        '[$selectedSources]. available=[$summary]');
  }
}
