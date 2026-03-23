import 'dart:io';
import 'package:csv/csv.dart';
import 'package:path_provider/path_provider.dart';
import '../models/health_data_point.dart';

/// Service responsible for logging health data to CSV files
class DataLogger {
  static final DataLogger _instance = DataLogger._internal();
  factory DataLogger() => _instance;
  DataLogger._internal();

  File? _currentFile;
  final List<HealthDataPoint> _buffer = [];
  static const int _bufferSize = 10; // Write to file every 10 data points

  /// Initialize the logger and create/open the CSV file
  Future<void> initialize() async {
    final directory = await getApplicationDocumentsDirectory();
    final fileName = 'health_data_${DateTime.now().millisecondsSinceEpoch}.csv';
    _currentFile = File('${directory.path}/$fileName');

    // Create file with headers if it doesn't exist
    if (!await _currentFile!.exists()) {
      await _currentFile!.create(recursive: true);
      await _writeHeaders();
    }
  }

  /// Write CSV headers
  Future<void> _writeHeaders() async {
    if (_currentFile == null) return;
    
    const headers = ['Timestamp', 'DataType', 'Value', 'Unit', 'Source'];
    final csv = const ListToCsvConverter().convert([headers]);
    await _currentFile!.writeAsString(csv, mode: FileMode.append);
  }

  /// Log a single health data point
  Future<void> logDataPoint(HealthDataPoint dataPoint) async {
    _buffer.add(dataPoint);

    // Flush buffer if it reaches the threshold
    if (_buffer.length >= _bufferSize) {
      await _flushBuffer();
    }
  }

  /// Log multiple health data points
  Future<void> logDataPoints(List<HealthDataPoint> dataPoints) async {
    _buffer.addAll(dataPoints);

    // Flush buffer if it reaches the threshold
    if (_buffer.length >= _bufferSize) {
      await _flushBuffer();
    }
  }

  /// Flush the buffer to the CSV file
  Future<void> _flushBuffer() async {
    if (_currentFile == null || _buffer.isEmpty) return;

    try {
      final rows = _buffer.map((point) => point.toCsvRow()).toList();
      final csv = const ListToCsvConverter().convert(rows);
      await _currentFile!.writeAsString(csv, mode: FileMode.append);
      _buffer.clear();
    } catch (e) {
      print('Error flushing buffer: $e');
    }
  }

  /// Force flush the buffer (useful when stopping collection)
  Future<void> flush() async {
    await _flushBuffer();
  }

  /// Get the current log file path
  String? getCurrentFilePath() {
    return _currentFile?.path;
  }

  /// Get all log files
  Future<List<File>> getAllLogFiles() async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final files = directory
          .listSync()
          .whereType<File>()
          .where((file) => file.path.endsWith('.csv'))
          .toList();
      
      // Sort by modification time (newest first)
      files.sort((a, b) => b.lastModifiedSync().compareTo(a.lastModifiedSync()));
      return files;
    } catch (e) {
      print('Error getting log files: $e');
      return [];
    }
  }

  /// Get the total number of samples across all files
  Future<int> getTotalSampleCount() async {
    try {
      final files = await getAllLogFiles();
      int totalCount = 0;

      for (final file in files) {
        final lines = await file.readAsLines();
        // Subtract 1 for header row
        totalCount += lines.length > 1 ? lines.length - 1 : 0;
      }

      // Add buffered samples
      totalCount += _buffer.length;

      return totalCount;
    } catch (e) {
      print('Error counting samples: $e');
      return _buffer.length;
    }
  }

  /// Create a new log file (useful for starting a new session)
  Future<void> createNewLogFile() async {
    await _flushBuffer();
    await initialize();
  }

  /// Delete all log files
  Future<void> deleteAllLogs() async {
    try {
      final files = await getAllLogFiles();
      for (final file in files) {
        await file.delete();
      }
      _buffer.clear();
    } catch (e) {
      print('Error deleting logs: $e');
    }
  }
}
