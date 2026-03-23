# Health Data Collector: Application Documentation

## 1. Purpose
This Flutter application collects wearable health metrics (from Health Connect), logs them to CSV in the background, shows live metrics on a dashboard, and provides an AI-assisted depression risk screening flow.

Primary workflow:
1. On first run, complete permission setup.
2. Open depression prediction home screen.
3. Optionally open dashboard for live stats and collection controls.
4. Start/stop background collection.
5. Export CSV logs.

## 2. High-Level Architecture
Core layers:
- UI screens: user interaction, display, navigation.
- Services: Health Connect access, background task orchestration, CSV logging.
- Models: typed structures for health samples and dashboard aggregates.

Main code areas:
- `lib/main.dart`
- `lib/screens/startup_router_screen.dart`
- `lib/screens/permission_gateway_screen.dart`
- `lib/screens/dashboard_screen.dart`
- `lib/screens/depression_detection_screen.dart`
- `lib/services/health_service.dart`
- `lib/services/foreground_service.dart`
- `lib/services/data_logger.dart`
- `lib/models/health_data_point.dart`

## 3. Startup and Navigation Flow
### 3.1 App Entry
`lib/main.dart`
- Initializes Flutter bindings.
- Locks orientation to portrait.
- Applies a dark Material 3 theme.
- Launches `StartupRouterScreen` as the first screen.

### 3.2 Startup Router
`lib/screens/startup_router_screen.dart`
- Reads a persisted flag (`permission_setup_completed`) from shared preferences.
- Routes first-time users to `PermissionGatewayScreen`.
- Routes returning users directly to `DepressionDetectionScreen` (home page).

### 3.3 Permission Gateway
`lib/screens/permission_gateway_screen.dart`
- Checks two permission groups:
  - `Permission.sensors` (body sensors).
  - Health Connect access via `HealthService.hasPermissions()`.
- When permissions are confirmed, persists setup-complete state.
- Navigates to `DepressionDetectionScreen`.
- If not granted, user taps `Grant Permissions` to request access.
- After grant, user can tap `Check Again` to revalidate and continue.

### 3.4 Dashboard
`lib/screens/dashboard_screen.dart`
- Initializes logger and foreground service.
- Refreshes health stats every 5 seconds.
- Provides 3 key actions:
  - Start/Stop background collection.
  - Export CSV.
  - Open depression risk screen.

### 3.5 Depression Risk Screen
`lib/screens/depression_detection_screen.dart`
- Prefills health fields from wearable data.
- Lets user add free-text mood/thought input.
- Calls remote model endpoint and shows risk result card.
- Acts as home/root screen after first-time setup.
- Includes a dashboard shortcut icon when shown as root.

## 4. Health Data Pipeline
### 4.1 Permission and Data Access
`lib/services/health_service.dart`
- Requests permissions for:
  - `STEPS`
  - `HEART_RATE`
  - `ACTIVE_ENERGY_BURNED`
  - `SLEEP_SESSION`
  - `HEART_RATE_VARIABILITY_RMSSD`
- Converts package `HealthDataPoint` values into app-level model fields.

### 4.2 Live Metrics for Dashboard
`lib/services/health_service.dart` methods used by dashboard:
- `getLatestHeartRate()`
- `getTodaySteps()`
- `getTodayCalories()`
- `getLatestHRV()`
- `getLastNightSleep()`

Dashboard uses these to populate `HealthStats` (`lib/models/health_data_point.dart`).

### 4.3 Background Collection
`lib/services/foreground_service.dart`
- Uses `flutter_foreground_task`.
- Starts a foreground service and task handler.
- Task handler collects health data every 5 minutes.
- Pulls data for the last 5-minute window and appends to logger buffer.
- Updates persistent notification with heart rate and sample count.

### 4.4 CSV Logging
`lib/services/data_logger.dart`
- Creates a session CSV in app documents directory:
  - `health_data_<timestamp>.csv`
- Writes header row once.
- Buffers samples and flushes every 10 points.
- Supports explicit `flush()` when collection stops.
- Supports listing all CSV files and counting total samples.

## 5. Depression Screening Flow (Detailed)
`lib/screens/depression_detection_screen.dart`

### Input data assembled for prediction
1. User text input.
2. Steps.
3. Sleep hours.
4. Active minutes.
5. Calories.
6. Heart rate.
7. HRV score.
8. Stress score.
9. Sleep HRV.

### API sequence
1. `POST /call/predict` with JSON payload `{ "data": [...] }`.
2. Parse `event_id` from response.
3. Wait briefly, then `GET /call/predict/<event_id>`.
4. Parse SSE-like response lines prefixed by `data: `.
5. Derive risk level based on returned text:
  - Contains `HIGH RISK` -> high risk UI.
  - Contains `LOW RISK` -> low risk UI.
  - Otherwise -> generic result UI.

### Error handling
- Non-200 response -> server error message.
- Missing parsed result -> fallback message.
- Network exception -> connection error message.

## 6. Data Model
`lib/models/health_data_point.dart`

### `HealthDataPoint`
Fields:
- `timestamp`
- `dataType`
- `value`
- `unit`
- `source`

Helpers:
- `toCsvRow()` for CSV output.
- `toMap()` and `fromMap()` for serialization.

### `HealthStats`
Aggregated dashboard metrics:
- `totalSamples`
- `currentHeartRate`
- `todaySteps`
- `todayCalories`
- `sleepMinutes`
- `avgHeartRate`
- `hrVariability`

## 7. Android Permissions and Platform Setup
`android/app/src/main/AndroidManifest.xml`

Important declarations include:
- Health Connect read/write permissions for steps, heart rate, HRV, sleep, and active calories.
- Body sensor permissions.
- Foreground service permissions (`FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_HEALTH`).
- Notification and wake lock permissions.
- Foreground service declaration:
  - `com.pravera.flutter_foreground_task.service.ForegroundService`
  - `android:foregroundServiceType="health"`
- Health Connect rationale and permission usage activity metadata.

## 8. Dependencies
`pubspec.yaml`

Primary runtime dependencies:
- `health`
- `flutter_foreground_task`
- `path_provider`
- `csv`
- `share_plus`
- `permission_handler`
- `intl`
- `http`
- `shared_preferences`

## 9. Typical User Scenario
1. User opens app.
2. If first run, permission gateway requests required permissions.
3. User lands on depression prediction home screen.
4. User can open dashboard to see live wearable data and control collection.
5. Background collection logs data every 5 minutes when started.
6. User exports the latest CSV when needed.

## 10. Operational Notes
- Foreground service can continue while app is not in foreground.
- Health data availability depends on wearable sync freshness.
- CSV files are session-based and sorted newest-first for export.
- Depression screen is a screening aid and not a medical diagnosis.

## 11. Quick Developer Commands
From workspace root:

```bash
flutter pub get
flutter analyze
flutter run
flutter test
```
