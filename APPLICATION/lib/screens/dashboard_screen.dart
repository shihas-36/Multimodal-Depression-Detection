import 'dart:async';
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import '../models/health_data_point.dart';
import '../services/health_service.dart';
import '../services/data_logger.dart';
import '../services/foreground_service.dart';
import 'depression_detection_screen.dart';

/// Main dashboard screen showing live health data and always-on collection status
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with TickerProviderStateMixin {
  final HealthService _healthService = HealthService();
  final DataLogger _dataLogger = DataLogger();
  final ForegroundService _foregroundService = ForegroundService();

  HealthStats _stats = HealthStats();
  bool _isCollecting = false;
  bool _isUpdatingStats = false;
  Timer? _updateTimer;
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _initializeServices();
    _startPeriodicUpdates();

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _updateTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _initializeServices() async {
    await _dataLogger.initialize();
    await _foregroundService.initialize();
    await _foregroundService.updateRunningStatus();

    var running = _foregroundService.isRunning();
    if (!running) {
      running = await _foregroundService.startService();
    }

    if (mounted) {
      setState(() {
        _isCollecting = running;
      });
    }

    if (!running && mounted) {
      _showSnackBar('Auto collection could not start. Check permissions.');
    }

    await _updateStats();
  }

  void _startPeriodicUpdates() {
    _updateTimer = Timer.periodic(const Duration(seconds: 5), (timer) {
      _updateStats();
    });
  }

  Future<void> _updateStats() async {
    if (_isUpdatingStats) return;
    _isUpdatingStats = true;

    try {
      final heartRate = await _healthService.getLatestHeartRate();
      final steps = await _healthService.getTodaySteps();
      final calories = await _healthService.getTodayCalories();
      final hrv = await _healthService.getLatestHRV();
      final sleep = await _healthService.getLastNightSleep();
      final totalSamples = await _dataLogger.getTotalSampleCount();

      if (mounted) {
        setState(() {
          _stats = HealthStats(
            totalSamples: totalSamples,
            currentHeartRate: heartRate,
            todaySteps: steps,
            todayCalories: calories,
            hrVariability: hrv,
            sleepMinutes: sleep,
          );
        });
      }
    } catch (e) {
      print('Error updating stats: $e');
    } finally {
      _isUpdatingStats = false;
    }
  }

  Future<void> _exportData() async {
    try {
      final files = await _dataLogger.getAllLogFiles();

      if (files.isEmpty) {
        _showSnackBar('No data to export');
        return;
      }

      // Share the most recent file
      final file = files.first;
      await Share.shareXFiles(
        [XFile(file.path)],
        subject: 'Health Data Export',
        text: 'Health data collected from ${file.path.split('/').last}',
      );
    } catch (e) {
      _showSnackBar('Error exporting data: $e');
    }
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Colors.blue.shade900,
              Colors.purple.shade900,
            ],
          ),
        ),
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: _updateStats,
            color: Colors.white,
            backgroundColor: Colors.purple.shade900,
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildHeader(),
                  const SizedBox(height: 30),
                  _buildHeartRateCard(),
                  const SizedBox(height: 20),
                  _buildStatsGrid(),
                  const SizedBox(height: 20),
                  _buildCollectionCard(),
                  const SizedBox(height: 20),
                  _buildActionButtons(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Health Dashboard',
          style: TextStyle(
            fontSize: 32,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Real-time health monitoring',
          style: TextStyle(
            fontSize: 16,
            color: Colors.white.withOpacity(0.7),
          ),
        ),
      ],
    );
  }

  Widget _buildHeartRateCard() {
    final heartRate = _stats.currentHeartRate;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.red.shade400,
            Colors.pink.shade600,
          ],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.red.withOpacity(0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, child) {
              return Transform.scale(
                scale: 1.0 + (_pulseController.value * 0.1),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.2),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.favorite,
                    color: Colors.white,
                    size: 40,
                  ),
                ),
              );
            },
          ),
          const SizedBox(width: 24),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Heart Rate',
                  style: TextStyle(
                    fontSize: 16,
                    color: Colors.white.withOpacity(0.9),
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  heartRate != null ? '${heartRate.toInt()}' : '--',
                  style: const TextStyle(
                    fontSize: 48,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                Text(
                  'BPM',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.white.withOpacity(0.7),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatsGrid() {
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 16,
      crossAxisSpacing: 16,
      childAspectRatio: 1.3,
      children: [
        _buildStatCard(
          icon: Icons.directions_walk,
          title: 'Steps',
          value: _stats.todaySteps?.toString() ?? '--',
          unit: 'today',
          color: Colors.green,
        ),
        _buildStatCard(
          icon: Icons.local_fire_department,
          title: 'Calories',
          value: _stats.todayCalories?.toStringAsFixed(0) ?? '--',
          unit: 'kcal',
          color: Colors.orange,
        ),
        _buildStatCard(
          icon: Icons.bedtime,
          title: 'Sleep',
          value: _stats.sleepMinutes != null
              ? '${(_stats.sleepMinutes! / 60).toStringAsFixed(1)}'
              : '--',
          unit: 'hours',
          color: Colors.indigo,
        ),
        _buildStatCard(
          icon: Icons.analytics,
          title: 'HRV',
          value: _stats.hrVariability?.toStringAsFixed(1) ?? '--',
          unit: 'ms',
          color: Colors.teal,
        ),
      ],
    );
  }

  Widget _buildStatCard({
    required IconData icon,
    required String title,
    required String value,
    required String unit,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: Colors.white.withOpacity(0.2),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Icon(icon, color: color, size: 28),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  unit,
                  style: TextStyle(
                    fontSize: 10,
                    color: color,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                value,
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              Text(
                title,
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.white.withOpacity(0.7),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCollectionCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: Colors.white.withOpacity(0.2),
          width: 1,
        ),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Data Collection',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _isCollecting ? 'Always Active' : 'Auto-start Failed',
                    style: TextStyle(
                      fontSize: 14,
                      color: _isCollecting ? Colors.green : Colors.red,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: _isCollecting ? Colors.green : Colors.red,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: (_isCollecting ? Colors.green : Colors.red)
                          .withOpacity(0.5),
                      blurRadius: 8,
                      spreadRadius: 2,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              const Icon(
                Icons.storage,
                color: Colors.white70,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Total Samples: ${_stats.totalSamples}',
                style: const TextStyle(
                  fontSize: 16,
                  color: Colors.white70,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons() {
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          height: 56,
          child: OutlinedButton(
            onPressed: _exportData,
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.white,
              side: const BorderSide(color: Colors.white, width: 2),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.share),
                SizedBox(width: 8),
                Text(
                  'Export CSV',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          height: 56,
          child: ElevatedButton(
            onPressed: () async {
              _updateTimer?.cancel();
              await Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => const DepressionDetectionScreen(),
                ),
              );
              if (!mounted) return;
              _startPeriodicUpdates();
              await _updateStats();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.deepPurple.shade400,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              elevation: 8,
            ),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.psychology_alt),
                SizedBox(width: 8),
                Text(
                  'Check Depression Risk',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
