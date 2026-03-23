import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/health_service.dart';
import 'depression_detection_screen.dart';

/// Permission gateway screen to ensure all required permissions are granted
class PermissionGatewayScreen extends StatefulWidget {
  const PermissionGatewayScreen({super.key});

  @override
  State<PermissionGatewayScreen> createState() =>
      _PermissionGatewayScreenState();
}

class _PermissionGatewayScreenState extends State<PermissionGatewayScreen> {
  static const _permissionSetupKey = 'permission_setup_completed';
  final HealthService _healthService = HealthService();
  bool _isChecking = true;
  bool _hasPermissions = false;
  bool _isRequesting = false;

  @override
  void initState() {
    super.initState();
    _checkPermissions();
  }

  Future<void> _checkPermissions() async {
    setState(() => _isChecking = true);

    final sensorsGranted = await Permission.sensors.isGranted;
    final healthGranted = await _healthService.hasPermissions();

    setState(() {
      _hasPermissions = sensorsGranted && healthGranted;
      _isChecking = false;
    });

    if (_hasPermissions) {
      await _markPermissionSetupCompleted();
      _navigateToHome();
    }
  }

  Future<void> _requestPermissions() async {
    setState(() {
      _isRequesting = true;
    });

    // Ask system / Health Connect for permission
    final granted = await _healthService.requestPermissions();

    // If user denied at UI level
    if (!granted) {
      setState(() => _isRequesting = false);
      _showPermissionDeniedDialog();
      return;
    }

    // IMPORTANT:
    // Do NOT check permission immediately.
    // Health Connect needs time to activate access.

    setState(() => _isRequesting = false);

    _showSnackBar(
      'Permission granted. Health Connect is syncing. Please tap "Check Again" in a moment.',
    );
  }

  Future<void> _markPermissionSetupCompleted() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_permissionSetupKey, true);
  }

  void _navigateToHome() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const DepressionDetectionScreen()),
    );
  }

  void _showPermissionDeniedDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Permissions Required'),
        content: const Text(
          'This app requires access to your health data and body sensors to function. '
          'Please grant the necessary permissions.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
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
          child: LayoutBuilder(
            builder: (context, constraints) {
              return SingleChildScrollView(
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: constraints.maxHeight,
                  ),
                  child: Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          // App Icon
                          Container(
                            width: 120,
                            height: 120,
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(30),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withOpacity(0.3),
                                  blurRadius: 20,
                                  offset: const Offset(0, 10),
                                ),
                              ],
                            ),
                            child: const Icon(
                              Icons.favorite,
                              size: 60,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 40),

                          // Title
                          const Text(
                            'Health Data Collector',
                            style: TextStyle(
                              fontSize: 32,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 16),

                          // Subtitle
                          Text(
                            'Collect health data from your Samsung Galaxy Watch for ML analysis',
                            style: TextStyle(
                              fontSize: 16,
                              color: Colors.white.withOpacity(0.8),
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 60),

                          // Permission Cards
                          _buildPermissionCard(
                            icon: Icons.sensors,
                            title: 'Body Sensors',
                            description:
                                'Access to heart rate and other sensor data',
                          ),
                          const SizedBox(height: 16),
                          _buildPermissionCard(
                            icon: Icons.health_and_safety,
                            title: 'Health Connect',
                            description:
                                'Read steps, sleep, calories, and HRV data',
                          ),
                          const SizedBox(height: 40),

                          // Action Button
                          if (_isChecking)
                            const CircularProgressIndicator(
                              valueColor:
                                  AlwaysStoppedAnimation<Color>(Colors.white),
                            )
                          else if (_isRequesting)
                            const CircularProgressIndicator(
                              valueColor:
                                  AlwaysStoppedAnimation<Color>(Colors.white),
                            )
                          else
                            Center(
                              child: Column(
                                children: [
                                  ElevatedButton(
                                    onPressed: _requestPermissions,
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: Colors.white,
                                      foregroundColor: Colors.purple.shade900,
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 48,
                                        vertical: 16,
                                      ),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(30),
                                      ),
                                      elevation: 8,
                                    ),
                                    child: const Text(
                                      'Grant Permissions',
                                      style: TextStyle(
                                        fontSize: 18,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 16),
                                  TextButton.icon(
                                    onPressed: openAppSettings,
                                    icon: const Icon(Icons.settings,
                                        color: Colors.white70),
                                    label: const Text(
                                      'Open Settings',
                                      style: TextStyle(color: Colors.white70),
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  TextButton.icon(
                                    onPressed: _checkPermissions,
                                    icon: const Icon(Icons.refresh,
                                        color: Colors.white70),
                                    label: const Text(
                                      'Check Again',
                                      style: TextStyle(color: Colors.white70),
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  ElevatedButton(
                                    onPressed: _navigateToHome,
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: Colors.greenAccent,
                                      foregroundColor: Colors.black,
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 48,
                                        vertical: 16,
                                      ),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(30),
                                      ),
                                      elevation: 8,
                                    ),
                                    child: const Text(
                                      'Start',
                                      style: TextStyle(
                                        fontSize: 18,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildPermissionCard({
    required IconData icon,
    required String title,
    required String description,
  }) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Colors.white.withOpacity(0.2),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              icon,
              color: Colors.white,
              size: 32,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
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
}
