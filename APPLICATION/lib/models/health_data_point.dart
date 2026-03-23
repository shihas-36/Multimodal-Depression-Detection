import 'package:intl/intl.dart';

/// Represents a single health data point collected from the device
class HealthDataPoint {
  final DateTime timestamp;
  final String dataType;
  final dynamic value;
  final String unit;
  final String? source;

  HealthDataPoint({
    required this.timestamp,
    required this.dataType,
    required this.value,
    required this.unit,
    this.source,
  });

  /// Convert to CSV row format
  List<String> toCsvRow() {
    final dateFormat = DateFormat('yyyy-MM-dd HH:mm:ss');
    return [
      dateFormat.format(timestamp),
      dataType,
      value.toString(),
      unit,
      source ?? 'unknown',
    ];
  }

  /// Convert to Map for JSON serialization
  Map<String, dynamic> toMap() {
    return {
      'timestamp': timestamp.toIso8601String(),
      'dataType': dataType,
      'value': value,
      'unit': unit,
      'source': source,
    };
  }

  /// Create from Map
  factory HealthDataPoint.fromMap(Map<String, dynamic> map) {
    return HealthDataPoint(
      timestamp: DateTime.parse(map['timestamp']),
      dataType: map['dataType'],
      value: map['value'],
      unit: map['unit'],
      source: map['source'],
    );
  }

  @override
  String toString() {
    return 'HealthDataPoint(timestamp: $timestamp, dataType: $dataType, value: $value, unit: $unit)';
  }
}

/// Represents aggregated health statistics
class HealthStats {
  int totalSamples;
  double? currentHeartRate;
  int? todaySteps;
  double? todayCalories;
  int? sleepMinutes;
  double? avgHeartRate;
  double? hrVariability;

  HealthStats({
    this.totalSamples = 0,
    this.currentHeartRate,
    this.todaySteps,
    this.todayCalories,
    this.sleepMinutes,
    this.avgHeartRate,
    this.hrVariability,
  });

  HealthStats copyWith({
    int? totalSamples,
    double? currentHeartRate,
    int? todaySteps,
    double? todayCalories,
    int? sleepMinutes,
    double? avgHeartRate,
    double? hrVariability,
  }) {
    return HealthStats(
      totalSamples: totalSamples ?? this.totalSamples,
      currentHeartRate: currentHeartRate ?? this.currentHeartRate,
      todaySteps: todaySteps ?? this.todaySteps,
      todayCalories: todayCalories ?? this.todayCalories,
      sleepMinutes: sleepMinutes ?? this.sleepMinutes,
      avgHeartRate: avgHeartRate ?? this.avgHeartRate,
      hrVariability: hrVariability ?? this.hrVariability,
    );
  }
}
