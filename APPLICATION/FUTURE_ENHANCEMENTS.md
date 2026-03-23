# Future Enhancements Guide

This document provides code snippets and guidance for implementing additional features.

## 1. LF/HF Ratio Calculation from RR-Intervals

To calculate Low Frequency / High Frequency ratio for HRV analysis:

### Add to `pubspec.yaml`:
```yaml
dependencies:
  fftea: ^1.0.0  # For FFT calculations
```

### Create `lib/utils/hrv_calculator.dart`:
```dart
import 'dart:math';

class HRVCalculator {
  /// Calculate LF/HF ratio from RR intervals
  /// RR intervals should be in milliseconds
  static Map<String, double> calculateFrequencyDomain(List<double> rrIntervals) {
    if (rrIntervals.length < 60) {
      throw Exception('Need at least 60 RR intervals for accurate calculation');
    }
    
    // Resample to 4Hz (standard for HRV analysis)
    final resampledData = _resample(rrIntervals, 4.0);
    
    // Apply Hamming window
    final windowedData = _applyHammingWindow(resampledData);
    
    // Perform FFT
    final fftResult = _performFFT(windowedData);
    
    // Calculate power in frequency bands
    final lfPower = _calculateBandPower(fftResult, 0.04, 0.15, 4.0);
    final hfPower = _calculateBandPower(fftResult, 0.15, 0.4, 4.0);
    
    return {
      'lf': lfPower,
      'hf': hfPower,
      'lf_hf_ratio': lfPower / hfPower,
    };
  }
  
  static List<double> _resample(List<double> data, double targetHz) {
    // Implement resampling logic
    // This is a simplified version
    return data;
  }
  
  static List<double> _applyHammingWindow(List<double> data) {
    final n = data.length;
    final windowed = <double>[];
    
    for (int i = 0; i < n; i++) {
      final window = 0.54 - 0.46 * cos(2 * pi * i / (n - 1));
      windowed.add(data[i] * window);
    }
    
    return windowed;
  }
  
  static List<double> _performFFT(List<double> data) {
    // Use fftea package here
    // This is a placeholder
    return data;
  }
  
  static double _calculateBandPower(
    List<double> fft,
    double lowFreq,
    double highFreq,
    double sampleRate,
  ) {
    // Calculate power in frequency band
    return 0.0; // Placeholder
  }
}
```

## 2. Cloud Sync with Firebase

### Add to `pubspec.yaml`:
```yaml
dependencies:
  firebase_core: ^3.6.0
  firebase_storage: ^12.3.4
  firebase_auth: ^5.3.1
```

### Create `lib/services/cloud_sync_service.dart`:
```dart
import 'dart:io';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'data_logger.dart';

class CloudSyncService {
  final FirebaseStorage _storage = FirebaseStorage.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;
  
  Future<void> syncToCloud() async {
    final user = _auth.currentUser;
    if (user == null) {
      throw Exception('User not authenticated');
    }
    
    final files = await DataLogger().getAllLogFiles();
    
    for (final file in files) {
      await _uploadFile(file, user.uid);
    }
  }
  
  Future<void> _uploadFile(File file, String userId) async {
    final fileName = file.path.split('/').last;
    final ref = _storage.ref().child('health_data/$userId/$fileName');
    
    await ref.putFile(file);
    print('Uploaded: $fileName');
  }
}
```

## 3. Data Visualization Charts

### Add to `pubspec.yaml`:
```yaml
dependencies:
  fl_chart: ^0.69.0
```

### Create `lib/widgets/heart_rate_chart.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';

class HeartRateChart extends StatelessWidget {
  final List<double> heartRateData;
  final List<DateTime> timestamps;
  
  const HeartRateChart({
    super.key,
    required this.heartRateData,
    required this.timestamps,
  });
  
  @override
  Widget build(BuildContext context) {
    return Container(
      height: 200,
      padding: const EdgeInsets.all(16),
      child: LineChart(
        LineChartData(
          gridData: FlGridData(show: true),
          titlesData: FlTitlesData(show: true),
          borderData: FlBorderData(show: true),
          lineBarsData: [
            LineChartBarData(
              spots: _createSpots(),
              isCurved: true,
              color: Colors.red,
              barWidth: 3,
              dotData: FlDotData(show: false),
            ),
          ],
        ),
      ),
    );
  }
  
  List<FlSpot> _createSpots() {
    return List.generate(
      heartRateData.length,
      (index) => FlSpot(index.toDouble(), heartRateData[index]),
    );
  }
}
```

## 4. Custom Collection Intervals

### Modify `lib/services/foreground_service.dart`:

Add a settings parameter:
```dart
class CollectionSettings {
  final Duration interval;
  final bool collectOnlyWhenActive;
  
  const CollectionSettings({
    this.interval = const Duration(minutes: 5),
    this.collectOnlyWhenActive = false,
  });
}

// In HealthDataTaskHandler:
@override
void onStart(DateTime timestamp, TaskStarter starter) {
  final settings = CollectionSettings(
    interval: const Duration(minutes: 1), // Custom interval
  );
  
  _timer = Timer.periodic(settings.interval, (timer) async {
    await _collectHealthData();
  });
}
```

## 5. Real-time ML Predictions

### Add to `pubspec.yaml`:
```yaml
dependencies:
  tflite_flutter: ^0.10.4
```

### Create `lib/services/ml_service.dart`:
```dart
import 'package:tflite_flutter/tflite_flutter.dart';

class MLService {
  Interpreter? _interpreter;
  
  Future<void> loadModel() async {
    _interpreter = await Interpreter.fromAsset('model.tflite');
  }
  
  Future<Map<String, double>> predictStressLevel({
    required double heartRate,
    required double hrv,
    required int steps,
  }) async {
    if (_interpreter == null) {
      await loadModel();
    }
    
    // Prepare input
    final input = [
      [heartRate, hrv, steps.toDouble()]
    ];
    
    // Prepare output
    final output = List.filled(1, 0.0).reshape([1, 1]);
    
    // Run inference
    _interpreter!.run(input, output);
    
    return {
      'stress_level': output[0][0],
    };
  }
}
```

## 6. Export to Multiple Formats

### Create `lib/utils/export_service.dart`:
```dart
import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import '../models/health_data_point.dart';

class ExportService {
  /// Export to JSON format
  static Future<File> exportToJson(List<HealthDataPoint> data) async {
    final directory = await getApplicationDocumentsDirectory();
    final file = File('${directory.path}/health_data_${DateTime.now().millisecondsSinceEpoch}.json');
    
    final jsonData = data.map((point) => point.toMap()).toList();
    await file.writeAsString(jsonEncode(jsonData));
    
    return file;
  }
  
  /// Export to Excel-compatible CSV with headers
  static Future<File> exportToExcel(List<HealthDataPoint> data) async {
    final directory = await getApplicationDocumentsDirectory();
    final file = File('${directory.path}/health_data_${DateTime.now().millisecondsSinceEpoch}.csv');
    
    final buffer = StringBuffer();
    buffer.writeln('Timestamp,DataType,Value,Unit,Source');
    
    for (final point in data) {
      final row = point.toCsvRow();
      buffer.writeln(row.join(','));
    }
    
    await file.writeAsString(buffer.toString());
    return file;
  }
}
```

## 7. Notification Customization

### Enhance `lib/services/foreground_service.dart`:

```dart
Future<void> _updateNotification() async {
  final healthService = HealthService();
  final heartRate = await healthService.getLatestHeartRate();
  final steps = await healthService.getTodaySteps();
  
  final hrText = heartRate != null ? '${heartRate.toInt()} bpm' : 'N/A';
  final stepsText = steps != null ? '$steps steps' : 'N/A';
  
  FlutterForegroundTask.updateService(
    notificationTitle: 'Health Data Collection Active',
    notificationText: 'HR: $hrText | Steps: $stepsText | Samples: $_sampleCount',
    notificationButtons: [
      const NotificationButton(id: 'stop', text: 'Stop'),
      const NotificationButton(id: 'export', text: 'Export'),
    ],
  );
}

@override
void onNotificationButtonPressed(String id) {
  if (id == 'stop') {
    FlutterForegroundTask.stopService();
  } else if (id == 'export') {
    // Trigger export
  }
}
```

## 8. Data Filtering and Search

### Create `lib/utils/data_filter.dart`:
```dart
import '../models/health_data_point.dart';

class DataFilter {
  static List<HealthDataPoint> filterByType(
    List<HealthDataPoint> data,
    String dataType,
  ) {
    return data.where((point) => point.dataType == dataType).toList();
  }
  
  static List<HealthDataPoint> filterByDateRange(
    List<HealthDataPoint> data,
    DateTime start,
    DateTime end,
  ) {
    return data.where((point) {
      return point.timestamp.isAfter(start) && 
             point.timestamp.isBefore(end);
    }).toList();
  }
  
  static Map<String, List<HealthDataPoint>> groupByType(
    List<HealthDataPoint> data,
  ) {
    final grouped = <String, List<HealthDataPoint>>{};
    
    for (final point in data) {
      grouped.putIfAbsent(point.dataType, () => []).add(point);
    }
    
    return grouped;
  }
}
```

## 9. Settings Screen

### Create `lib/screens/settings_screen.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  int _collectionInterval = 5; // minutes
  bool _collectOnlyWhenActive = false;
  
  @override
  void initState() {
    super.initState();
    _loadSettings();
  }
  
  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _collectionInterval = prefs.getInt('collection_interval') ?? 5;
      _collectOnlyWhenActive = prefs.getBool('collect_only_active') ?? false;
    });
  }
  
  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('collection_interval', _collectionInterval);
    await prefs.setBool('collect_only_active', _collectOnlyWhenActive);
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        children: [
          ListTile(
            title: const Text('Collection Interval'),
            subtitle: Text('$_collectionInterval minutes'),
            trailing: DropdownButton<int>(
              value: _collectionInterval,
              items: [1, 5, 10, 15, 30].map((int value) {
                return DropdownMenuItem<int>(
                  value: value,
                  child: Text('$value min'),
                );
              }).toList(),
              onChanged: (value) {
                setState(() => _collectionInterval = value!);
                _saveSettings();
              },
            ),
          ),
          SwitchListTile(
            title: const Text('Collect Only When Active'),
            subtitle: const Text('Stop collection when screen is off'),
            value: _collectOnlyWhenActive,
            onChanged: (value) {
              setState(() => _collectOnlyWhenActive = value);
              _saveSettings();
            },
          ),
        ],
      ),
    );
  }
}
```

## 10. Error Logging and Crash Reporting

### Add to `pubspec.yaml`:
```yaml
dependencies:
  firebase_crashlytics: ^4.1.3
```

### Update `lib/main.dart`:
```dart
import 'package:firebase_crashlytics/firebase_crashlytics.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Firebase
  await Firebase.initializeApp();
  
  // Pass all uncaught errors to Crashlytics
  FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterError;
  
  runApp(const HealthDataCollectorApp());
}
```

---

## Implementation Priority

1. **High Priority**: Data visualization charts, Settings screen
2. **Medium Priority**: Cloud sync, Custom intervals
3. **Low Priority**: ML predictions, LF/HF calculations

Each enhancement can be implemented independently without affecting existing functionality.
