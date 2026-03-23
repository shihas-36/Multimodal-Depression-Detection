# Health Data Collector for Samsung Galaxy Watch

A Flutter application designed to collect health data from Samsung Galaxy Watch via Health Connect for Machine Learning projects.

## Features

### 📊 Data Collection
- **Steps**: Daily step count tracking
- **Heart Rate**: Real-time heart rate monitoring
- **HRV (RMSSD)**: Heart Rate Variability with RMSSD metric
- **Sleep Sessions**: Sleep duration and quality tracking
- **Active Calories**: Energy expenditure monitoring

### 🔄 Background Collection
- **Foreground Service**: Continuous data collection even when screen is off
- **Automatic Updates**: Data collected every 5 minutes
- **Persistent Notifications**: Shows current heart rate and sample count

### 💾 Data Storage
- **CSV Export**: All data saved in CSV format
- **Buffered Writing**: Efficient file I/O with automatic flushing
- **Multiple Files**: Separate CSV files for each collection session
- **Share Functionality**: Export data to Google Drive, Email, or other apps

### 🎨 User Interface
- **Permission Gateway**: Ensures all required permissions are granted
- **Live Dashboard**: Real-time display of health metrics
- **Animated Heart Rate**: Pulsing heart icon for visual feedback
- **Stats Grid**: Quick overview of steps, calories, sleep, and HRV
- **Collection Controls**: Start/Stop data collection with one tap

## Requirements

### Device Requirements
- Android device running Android 9.0 (API 28) or higher
- Samsung Galaxy Watch with Health Connect installed
- Health Connect app configured and synced

### Permissions Required
- Body Sensors (for heart rate monitoring)
- Health Connect permissions for:
  - Steps (Read/Write)
  - Heart Rate (Read/Write)
  - Heart Rate Variability (Read/Write)
  - Sleep Sessions (Read/Write)
  - Active Calories Burned (Read/Write)
- Foreground Service (for background collection)
- Notifications (for foreground service)

## Installation

### 1. Clone or Download the Project
```bash
cd c:\Programs\WEARABLES
```

### 2. Install Dependencies
```bash
flutter pub get
```

### 3. Configure Health Connect
Ensure your Samsung Galaxy Watch is paired and Health Connect is installed on your phone.

### 4. Build and Run
```bash
# For debug build
flutter run

# For release build
flutter build apk --release
```

## Project Structure

```
lib/
├── main.dart                          # App entry point
├── models/
│   └── health_data_point.dart        # Data models
├── services/
│   ├── health_service.dart           # Health Connect integration
│   ├── data_logger.dart              # CSV logging service
│   └── foreground_service.dart       # Background collection service
├── screens/
│   ├── permission_gateway_screen.dart # Permission request screen
│   └── dashboard_screen.dart         # Main dashboard
└── widgets/                          # Reusable widgets (if needed)
```

## Usage

### First Launch
1. Open the app
2. Grant Body Sensors permission when prompted
3. Grant Health Connect permissions for all requested data types
4. You'll be redirected to the dashboard

### Starting Data Collection
1. On the dashboard, tap "Start Collection"
2. The app will start a foreground service
3. Data will be collected every 5 minutes
4. A persistent notification will show collection status

### Viewing Live Data
- **Heart Rate**: Large animated card showing current BPM
- **Steps**: Today's step count
- **Calories**: Active calories burned today
- **Sleep**: Last night's sleep duration
- **HRV**: Latest heart rate variability reading
- **Total Samples**: Count of all collected data points

### Exporting Data
1. Tap "Export CSV" button
2. Choose where to share (Google Drive, Email, etc.)
3. The most recent CSV file will be shared

### CSV Format
The exported CSV files contain the following columns:
- **Timestamp**: Date and time of the reading (YYYY-MM-DD HH:MM:SS)
- **DataType**: Type of health metric (STEPS, HEART_RATE, etc.)
- **Value**: Numeric value of the reading
- **Unit**: Unit of measurement (bpm, steps, kcal, etc.)
- **Source**: Data source (Samsung Health, Google Fit, etc.)

## Technical Details

### Health Connect Integration
The app uses the `health` package (v11.1.0) to interact with Health Connect API. It specifically requests:
- `HealthDataType.STEPS`
- `HealthDataType.HEART_RATE`
- `HealthDataType.HEART_RATE_VARIABILITY_RMSSD`
- `HealthDataType.SLEEP_SESSION`
- `HealthDataType.ACTIVE_ENERGY_BURNED`

### Background Service
The foreground service uses `flutter_foreground_task` (v8.11.0) with:
- Service type: `health`
- Update interval: 5 minutes
- Wake lock enabled for reliable background operation
- Low-priority notification to minimize user distraction

### Data Processing
- **Buffered Writing**: Data is buffered in memory and written to disk every 10 samples
- **Automatic Flushing**: Buffer is flushed when stopping collection or app termination
- **File Management**: Each session creates a new CSV file with timestamp

## Troubleshooting

### No Data Appearing
1. Ensure Samsung Galaxy Watch is paired and synced
2. Check that Health Connect has recent data
3. Verify all permissions are granted
4. Try manually syncing your watch

### Background Collection Stops
1. Disable battery optimization for the app
2. Ensure "Allow background activity" is enabled
3. Check that foreground service notification is visible

### Permission Errors
1. Go to Settings > Apps > Health Data Collector > Permissions
2. Ensure all permissions are granted
3. Open Health Connect and verify app has access

### HRV Data Not Available
HRV (RMSSD) data requires:
- Samsung Galaxy Watch 4 or newer
- Recent firmware updates
- At least 24 hours of wear time for initial calculation

## Future Enhancements

- [ ] LF/HF ratio calculation from RR-intervals
- [ ] Cloud sync for automatic backup
- [ ] Data visualization charts
- [ ] Custom collection intervals
- [ ] Multiple watch support
- [ ] Real-time ML predictions

## Dependencies

- `health: ^11.1.0` - Health Connect integration
- `flutter_foreground_task: ^8.11.0` - Background service
- `path_provider: ^2.1.4` - File system access
- `csv: ^6.0.0` - CSV file generation
- `share_plus: ^10.1.2` - File sharing
- `permission_handler: ^11.3.1` - Permission management
- `intl: ^0.19.0` - Date/time formatting
- `provider: ^6.1.2` - State management

## License

This project is created for Machine Learning research purposes.

## Support

For issues or questions, please check:
1. Health Connect documentation
2. Samsung Galaxy Watch compatibility
3. Flutter health package documentation
