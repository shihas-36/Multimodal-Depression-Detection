import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/health_service.dart';
import 'depression_detection_screen.dart';
import 'permission_gateway_screen.dart';

/// Routes first-time users through permission setup, then opens home screen.
class StartupRouterScreen extends StatefulWidget {
  const StartupRouterScreen({super.key});

  @override
  State<StartupRouterScreen> createState() => _StartupRouterScreenState();
}

class _StartupRouterScreenState extends State<StartupRouterScreen> {
  static const _permissionSetupKey = 'permission_setup_completed';
  Widget? _startScreen;

  @override
  void initState() {
    super.initState();
    _resolveStartScreen();
  }

  Future<void> _resolveStartScreen() async {
    final prefs = await SharedPreferences.getInstance();
    final setupCompleted = prefs.getBool(_permissionSetupKey) ?? false;

    if (setupCompleted) {
      // Re-validate on every launch — permissions can be revoked at any time.
      final stillGranted = await HealthService().hasPermissions();
      if (!mounted) return;
      if (!stillGranted) {
        await prefs.remove(_permissionSetupKey);
        setState(() => _startScreen = const PermissionGatewayScreen());
        return;
      }
    }

    if (!mounted) return;
    setState(() {
      _startScreen = setupCompleted
          ? const DepressionDetectionScreen()
          : const PermissionGatewayScreen();
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_startScreen == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return _startScreen!;
  }
}
