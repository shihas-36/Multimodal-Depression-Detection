import 'dart:ui' show ImageFilter;
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dashboard_screen.dart';
import 'permission_gateway_screen.dart';
import '../services/health_service.dart';

class DepressionDetectionScreen extends StatefulWidget {
  const DepressionDetectionScreen({super.key});

  @override
  State<DepressionDetectionScreen> createState() =>
      _DepressionDetectionScreenState();
}

enum _RiskLevel { none, loading, low, high, unknown }

class _DepressionDetectionScreenState extends State<DepressionDetectionScreen> {
  final _healthService = HealthService();

  final _textController = TextEditingController();
  final _stepsController = TextEditingController();
  final _sleepController = TextEditingController();
  final _activeController = TextEditingController();
  final _caloriesController = TextEditingController();
  final _hrController = TextEditingController();
  final _hrvController = TextEditingController();
  final _stressController = TextEditingController();
  final _sleepHrvController = TextEditingController();

  _RiskLevel _riskLevel = _RiskLevel.none;
  String _resultDetail = '';
  bool _loadingData = true;
  bool _permissionDenied = false;
  bool _permissionsVerified = false;
  int _prefillCount = 0;
  bool _debugLoading = false;
  DateTime? _lastPrefillAttempt;
  Map<String, String> _readDiagnostics = {};
  final Set<TextEditingController> _prefilledControllers = {};

  @override
  void initState() {
    super.initState();
    _prefillHealthData();
  }

  @override
  void dispose() {
    _textController.dispose();
    _stepsController.dispose();
    _sleepController.dispose();
    _activeController.dispose();
    _caloriesController.dispose();
    _hrController.dispose();
    _hrvController.dispose();
    _stressController.dispose();
    _sleepHrvController.dispose();
    super.dispose();
  }

  Future<void> _prefillHealthData() async {
    setState(() {
      _loadingData = true;
      _debugLoading = true;
      _lastPrefillAttempt = DateTime.now();
    });

    // Check permissions before attempting reads so we can show the right banner.
    final permitted = await _healthService.hasPermissions();
    if (!mounted) return;
    if (!permitted) {
      setState(() {
        _permissionDenied = true;
        _permissionsVerified = false;
        _readDiagnostics = {
          'Sensors permission': 'denied',
          'Health Connect permission': 'denied',
          'Steps': 'denied',
          'Sleep': 'denied',
          'Calories': 'denied',
          'Heart Rate': 'denied',
          'HRV': 'denied',
        };
        _loadingData = false;
        _debugLoading = false;
      });
      return;
    }

    final results = await Future.wait([
      _healthService.getTodaySteps(),
      _healthService.getLastNightSleep(),
      _healthService.getTodayCalories(),
      _healthService.getLatestHeartRate(),
      _healthService.getLatestHRV(),
    ]);

    if (!mounted) return;

    final steps = results[0] as int?;
    final sleepMinutes = results[1] as int?;
    final calories = results[2] as double?;
    final hr = results[3] as double?;
    final hrv = results[4] as double?;

    int count = 0;
    final Set<TextEditingController> filled = {};

    if (steps != null) {
      _stepsController.text = steps.toString();
      filled.add(_stepsController);
      count++;
    }
    if (sleepMinutes != null) {
      _sleepController.text = (sleepMinutes / 60.0).toStringAsFixed(1);
      filled.add(_sleepController);
      count++;
    }
    if (calories != null) {
      _caloriesController.text = calories.toStringAsFixed(0);
      filled.add(_caloriesController);
      count++;
    }
    if (hr != null) {
      _hrController.text = hr.toStringAsFixed(0);
      filled.add(_hrController);
      count++;
    }
    if (hrv != null) {
      _hrvController.text = hrv.toStringAsFixed(1);
      _sleepHrvController.text = hrv.toStringAsFixed(1);
      filled.add(_hrvController);
      filled.add(_sleepHrvController);
      count += 2;
    }

    final diagnostics = <String, String>{
      'Sensors permission': 'granted',
      'Health Connect permission': 'granted',
      'Steps': steps != null ? 'ok' : 'no_data',
      'Sleep': sleepMinutes != null ? 'ok' : 'no_data',
      'Calories': calories != null ? 'ok' : 'no_data',
      'Heart Rate': hr != null ? 'ok' : 'no_data',
      'HRV': hrv != null ? 'ok' : 'no_data',
    };

    setState(() {
      _permissionDenied = false;
      _permissionsVerified = true;
      _readDiagnostics = diagnostics;
      _prefillCount = count;
      _prefilledControllers
        ..clear()
        ..addAll(filled);
      _loadingData = false;
      _debugLoading = false;
    });
  }

  Future<void> _predict() async {
    const baseUrl = 'https://shihas-36-depression-detection.hf.space';
    const predictPath = '/gradio_api/call/predict';

    setState(() {
      _riskLevel = _RiskLevel.loading;
      _resultDetail = '';
    });

    try {
      final callResponse = await http.post(
        Uri.parse('$baseUrl$predictPath'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'data': [
            _textController.text,
            double.tryParse(_stepsController.text) ?? 0,
            double.tryParse(_sleepController.text) ?? 0,
            double.tryParse(_activeController.text) ?? 0,
            double.tryParse(_caloriesController.text) ?? 0,
            double.tryParse(_hrController.text) ?? 0,
            double.tryParse(_hrvController.text) ?? 0,
            double.tryParse(_stressController.text) ?? 0,
            double.tryParse(_sleepHrvController.text) ?? 0,
          ]
        }),
      );

      if (callResponse.statusCode != 200) {
        setState(() {
          _riskLevel = _RiskLevel.unknown;
          _resultDetail =
              'Server error ${callResponse.statusCode}. Please try again.';
        });
        return;
      }

      final callData = jsonDecode(callResponse.body);
      final String? eventId = callData['event_id'] as String?;
      if (eventId == null || eventId.isEmpty) {
        setState(() {
          _riskLevel = _RiskLevel.unknown;
          _resultDetail = 'Server did not return a valid event id.';
        });
        return;
      }

      // Gradio queues jobs asynchronously. Poll the event endpoint a few times
      // to avoid false negatives when inference takes longer than one request.
      String? predictionResult;
      for (int attempt = 0; attempt < 10; attempt++) {
        await Future.delayed(const Duration(milliseconds: 800));

        final resultResponse = await http.get(
          Uri.parse('$baseUrl$predictPath/$eventId'),
        );

        if (resultResponse.statusCode != 200) {
          continue;
        }

        for (final line in resultResponse.body.split('\n')) {
          if (!line.startsWith('data: ')) {
            continue;
          }

          final jsonStr = line.substring(6).trim();
          final decoded = jsonDecode(jsonStr);
          if (decoded is List && decoded.isNotEmpty) {
            predictionResult = decoded[0].toString();
            break;
          }
        }

        if (predictionResult != null) {
          break;
        }
      }

      if (predictionResult == null) {
        setState(() {
          _riskLevel = _RiskLevel.unknown;
          _resultDetail =
              'Prediction is still processing or unavailable. Please try again.';
        });
        return;
      }

      if (predictionResult.contains('HIGH RISK')) {
        setState(() {
          _riskLevel = _RiskLevel.high;
          _resultDetail = 'Please consult a licensed healthcare professional.';
        });
      } else if (predictionResult.contains('LOW RISK')) {
        setState(() {
          _riskLevel = _RiskLevel.low;
          _resultDetail = 'Keep maintaining your healthy habits!';
        });
      } else {
        setState(() {
          _riskLevel = _RiskLevel.unknown;
          _resultDetail = predictionResult!;
        });
      }
    } catch (e) {
      setState(() {
        _riskLevel = _RiskLevel.unknown;
        _resultDetail = 'Connection error. Check your network and try again.';
      });
    }
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    bool numeric = false,
    int maxLines = 1,
  }) {
    final isPrefilled = _prefilledControllers.contains(controller);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        keyboardType: numeric ? TextInputType.number : TextInputType.multiline,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: TextStyle(
            color: isPrefilled
                ? Colors.greenAccent.withOpacity(0.85)
                : Colors.white.withOpacity(0.7),
          ),
          prefixIcon:
              Icon(icon, color: Colors.white.withOpacity(0.6), size: 20),
          suffixIcon: isPrefilled
              ? const Icon(Icons.watch_rounded,
                  color: Colors.greenAccent, size: 16)
              : null,
          filled: true,
          fillColor: isPrefilled
              ? Colors.green.withOpacity(0.06)
              : Colors.white.withOpacity(0.08),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: isPrefilled
                ? BorderSide(
                    color: Colors.greenAccent.withOpacity(0.5), width: 1)
                : BorderSide(color: Colors.white.withOpacity(0.2), width: 1),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide:
                const BorderSide(color: Colors.purpleAccent, width: 1.5),
          ),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
      ),
    );
  }

  Widget _buildPrefillStatusBanner() {
    if (_loadingData) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          children: [
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(
                strokeWidth: 1.5,
                color: Colors.white54,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              'Fetching wearable data…',
              style: TextStyle(
                color: Colors.white.withOpacity(0.55),
                fontSize: 12,
              ),
            ),
          ],
        ),
      );
    }

    if (_permissionDenied) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: Colors.red.withOpacity(0.12),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.red.withOpacity(0.4)),
          ),
          child: Row(
            children: [
              const Icon(Icons.lock_outline_rounded,
                  color: Colors.redAccent, size: 16),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Health Connect permissions not granted. '
                  'Please grant access to auto-fill metrics.',
                  style: TextStyle(color: Colors.redAccent, fontSize: 12),
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: () {
                  Navigator.of(context).pushReplacement(
                    MaterialPageRoute(
                      builder: (_) => const PermissionGatewayScreen(),
                    ),
                  );
                },
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.redAccent.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                    border:
                        Border.all(color: Colors.redAccent.withOpacity(0.5)),
                  ),
                  child: const Text(
                    'Grant',
                    style: TextStyle(
                      color: Colors.redAccent,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    if (_prefillCount > 0) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          children: [
            const Icon(Icons.check_circle_rounded,
                color: Colors.greenAccent, size: 15),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                '$_prefillCount metric${_prefillCount == 1 ? '' : 's'} '
                'loaded from wearable — highlighted in green. Edit if needed.',
                style: const TextStyle(
                  color: Colors.greenAccent,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.watch_off_rounded,
                  color: Colors.orange.withOpacity(0.8), size: 15),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  _permissionsVerified
                      ? 'Permissions are granted, but no recent wearable records were returned.'
                      : 'No wearable data available. Please enter values manually.',
                  style: TextStyle(
                    color: Colors.orange.withOpacity(0.8),
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
          if (_permissionsVerified) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: () {
                setState(() => _loadingData = true);
                _prefillHealthData();
              },
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Re-check wearable data'),
              style: TextButton.styleFrom(
                foregroundColor: Colors.orange.withOpacity(0.8),
                textStyle: const TextStyle(fontSize: 11.5),
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _formatDebugTime(DateTime? time) {
    if (time == null) return 'Not checked yet';

    final local = time.toLocal();
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    final ss = local.second.toString().padLeft(2, '0');
    return '$hh:$mm:$ss';
  }

  Color _statusColor(String status) {
    if (status.startsWith('ok')) return Colors.greenAccent;
    if (status == 'granted') return Colors.greenAccent;
    if (status == 'no_data') return Colors.orange;
    if (status == 'denied') return Colors.redAccent;
    return Colors.white70;
  }

  Widget _buildDebugPanel() {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.2)),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          leading: const Icon(
            Icons.bug_report_outlined,
            color: Colors.white70,
            size: 18,
          ),
          title: const Text(
            'Debug Diagnostics',
            style: TextStyle(
              color: Colors.white70,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
          trailing: _debugLoading
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.8,
                    color: Colors.white54,
                  ),
                )
              : const Icon(Icons.expand_more, color: Colors.white54),
          children: [
            Row(
              children: [
                Text(
                  'Last check: ${_formatDebugTime(_lastPrefillAttempt)}',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.65),
                    fontSize: 11,
                  ),
                ),
                const Spacer(),
                TextButton.icon(
                  onPressed: _debugLoading
                      ? null
                      : () {
                          _prefillHealthData();
                        },
                  icon: const Icon(Icons.refresh, size: 14),
                  label: const Text('Run check'),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.white70,
                    textStyle: const TextStyle(fontSize: 11),
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            if (_readDiagnostics.isEmpty)
              Text(
                'No diagnostics yet.',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.6),
                  fontSize: 11,
                ),
              )
            else
              ..._readDiagnostics.entries.map((entry) {
                final status = entry.value;
                return Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          entry.key,
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.8),
                            fontSize: 11.5,
                          ),
                        ),
                      ),
                      Text(
                        status,
                        style: TextStyle(
                          color: _statusColor(status),
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard() {
    if (_riskLevel == _RiskLevel.none) return const SizedBox.shrink();

    if (_riskLevel == _RiskLevel.loading) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
          child: Container(
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Colors.white.withOpacity(0.20),
                  Colors.white.withOpacity(0.08),
                ],
              ),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white.withOpacity(0.35)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.18),
                  blurRadius: 22,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 2.6,
                  ),
                ),
                SizedBox(width: 14),
                Text(
                  'Analyzing your signal pattern...',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.2,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final List<Color> glassGradient;
    final Color accentColor;
    final Color softAccent;
    final IconData riskIcon;
    final String riskLabel;
    final String riskSubLabel;

    switch (_riskLevel) {
      case _RiskLevel.high:
        glassGradient = [
          Colors.redAccent.withOpacity(0.26),
          Colors.deepPurple.withOpacity(0.18),
        ];
        accentColor = const Color(0xFFFF7A8A);
        softAccent = const Color(0xFFFFD8DE);
        riskIcon = Icons.warning_rounded;
        riskLabel = 'HIGH RISK';
        riskSubLabel = 'Please consult a licensed healthcare professional.';
      case _RiskLevel.low:
        glassGradient = [
          Colors.greenAccent.withOpacity(0.22),
          Colors.cyanAccent.withOpacity(0.14),
        ];
        accentColor = const Color(0xFF73E28D);
        softAccent = const Color(0xFFCFF9D7);
        riskIcon = Icons.check_circle_rounded;
        riskLabel = 'LOW RISK';
        riskSubLabel = 'Keep maintaining your healthy habits!';
      default:
        glassGradient = [
          Colors.orangeAccent.withOpacity(0.25),
          Colors.pinkAccent.withOpacity(0.16),
        ];
        accentColor = const Color(0xFFFFC76A);
        softAccent = const Color(0xFFFFE7BF);
        riskIcon = Icons.info_rounded;
        riskLabel = 'RESULT';
        riskSubLabel = 'Interpretation available below.';
    }

    final detail = _resultDetail.isNotEmpty ? _resultDetail : riskSubLabel;

    return TweenAnimationBuilder<double>(
      duration: const Duration(milliseconds: 420),
      curve: Curves.easeOutCubic,
      tween: Tween(begin: 0.96, end: 1.0),
      builder: (context, scale, child) {
        return Transform.scale(scale: scale, child: child);
      },
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
          child: Container(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Colors.white.withOpacity(0.18),
                  Colors.white.withOpacity(0.05),
                ],
              ),
              borderRadius: BorderRadius.circular(24),
              border:
                  Border.all(color: Colors.white.withOpacity(0.40), width: 1),
              boxShadow: [
                BoxShadow(
                  color: accentColor.withOpacity(0.26),
                  blurRadius: 24,
                  spreadRadius: 1,
                  offset: const Offset(0, 12),
                ),
                BoxShadow(
                  color: Colors.black.withOpacity(0.14),
                  blurRadius: 26,
                  offset: const Offset(0, 14),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: double.infinity,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: glassGradient,
                    ),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: accentColor.withOpacity(0.55)),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 42,
                        height: 42,
                        decoration: BoxDecoration(
                          color: Colors.black.withOpacity(0.18),
                          shape: BoxShape.circle,
                          border:
                              Border.all(color: softAccent.withOpacity(0.65)),
                        ),
                        child: Icon(riskIcon, color: softAccent, size: 24),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Screening Result',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.88),
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                                letterSpacing: 0.4,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              riskLabel,
                              style: TextStyle(
                                color: softAccent,
                                fontSize: 22,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 1.1,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  detail,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.95),
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canPop = Navigator.of(context).canPop();

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
          child: Column(
            children: [
              // Header
              Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: () {
                        if (canPop) {
                          Navigator.of(context).pop();
                          return;
                        }

                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const DashboardScreen(),
                          ),
                        );
                      },
                      icon: Icon(
                        canPop ? Icons.arrow_back_ios_new : Icons.dashboard,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Depression Risk',
                            style: TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                          Text(
                            'AI-powered mental health screening',
                            style: TextStyle(
                              fontSize: 13,
                              color: Colors.white70,
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (_loadingData)
                      const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          color: Colors.white54,
                          strokeWidth: 2,
                        ),
                      ),
                  ],
                ),
              ),

              // Disclaimer banner
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: Colors.amber.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                        color: Colors.amber.withOpacity(0.4), width: 1),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.info_outline, color: Colors.amber, size: 18),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'This is a screening tool only and is not a medical diagnosis.',
                          style: TextStyle(
                            color: Colors.amber,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Scrollable form content
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Social media text section
                      _sectionLabel(
                          'How are you feeling?', Icons.chat_bubble_outline),
                      _buildTextField(
                        controller: _textController,
                        label: 'Describe your mood or recent thoughts…',
                        icon: Icons.edit_note,
                        maxLines: 4,
                      ),
                      const SizedBox(height: 8),

                      // Wearable metrics section
                      _sectionLabel(
                          'Health Metrics', Icons.monitor_heart_outlined),
                      _buildPrefillStatusBanner(),
                      _buildDebugPanel(),
                      const SizedBox(height: 12),

                      Row(
                        children: [
                          Expanded(
                            child: _buildTextField(
                              controller: _stepsController,
                              label: 'Steps',
                              icon: Icons.directions_walk,
                              numeric: true,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _buildTextField(
                              controller: _sleepController,
                              label: 'Sleep (hrs)',
                              icon: Icons.bedtime,
                              numeric: true,
                            ),
                          ),
                        ],
                      ),
                      Row(
                        children: [
                          Expanded(
                            child: _buildTextField(
                              controller: _caloriesController,
                              label: 'Calories',
                              icon: Icons.local_fire_department,
                              numeric: true,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _buildTextField(
                              controller: _activeController,
                              label: 'Active Mins',
                              icon: Icons.timer_outlined,
                              numeric: true,
                            ),
                          ),
                        ],
                      ),
                      Row(
                        children: [
                          Expanded(
                            child: _buildTextField(
                              controller: _hrController,
                              label: 'Heart Rate',
                              icon: Icons.favorite,
                              numeric: true,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _buildTextField(
                              controller: _hrvController,
                              label: 'HRV Score',
                              icon: Icons.analytics,
                              numeric: true,
                            ),
                          ),
                        ],
                      ),
                      Row(
                        children: [
                          Expanded(
                            child: _buildTextField(
                              controller: _stressController,
                              label: 'Stress (0–100)',
                              icon: Icons.psychology_outlined,
                              numeric: true,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _buildTextField(
                              controller: _sleepHrvController,
                              label: 'Sleep HRV',
                              icon: Icons.nightlight_round,
                              numeric: true,
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 8),

                      // Predict button
                      SizedBox(
                        width: double.infinity,
                        height: 56,
                        child: ElevatedButton(
                          onPressed: _riskLevel == _RiskLevel.loading
                              ? null
                              : _predict,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.purpleAccent.shade400,
                            foregroundColor: Colors.white,
                            disabledBackgroundColor:
                                Colors.purpleAccent.withOpacity(0.4),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                            elevation: 8,
                          ),
                          child: const Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.psychology_alt, size: 22),
                              SizedBox(width: 10),
                              Text(
                                'Analyze Depression Risk',
                                style: TextStyle(
                                    fontSize: 17, fontWeight: FontWeight.bold),
                              ),
                            ],
                          ),
                        ),
                      ),

                      const SizedBox(height: 20),

                      // Result card
                      _buildResultCard(),
                      const SizedBox(height: 32),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionLabel(String text, IconData icon) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Icon(icon, color: Colors.purpleAccent, size: 20),
          const SizedBox(width: 8),
          Text(
            text,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
