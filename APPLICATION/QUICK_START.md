# Quick Start Guide

## Prerequisites Checklist

Before running the app, ensure you have:

- [ ] Flutter SDK installed (3.6.0 or higher)
- [ ] Android device with Android 9.0+ (API 28+)
- [ ] Samsung Galaxy Watch paired with your phone
- [ ] Health Connect app installed on your phone
- [ ] Samsung Health syncing to Health Connect
- [ ] USB debugging enabled on your phone

## Step-by-Step Setup

### 1. Verify Flutter Installation
```bash
flutter doctor
```
Ensure all checks pass (especially Android toolchain).

### 2. Connect Your Device
```bash
# Check connected devices
flutter devices

# Should show your Android device
```

### 3. Install Dependencies
```bash
cd c:\Programs\WEARABLES
flutter pub get
```

### 4. Run the App
```bash
# Debug mode (recommended for first run)
flutter run

# Or release mode
flutter run --release
```

### 5. Grant Permissions
When the app launches:
1. Tap "Grant Permissions"
2. Allow "Body Sensors" permission
3. Allow all Health Connect permissions:
   - Steps
   - Heart Rate
   - Heart Rate Variability
   - Sleep
   - Active Calories Burned

### 6. Start Collecting Data
1. On the dashboard, tap "Start Collection"
2. Allow notification permission if prompted
3. Disable battery optimization if prompted
4. The app will now collect data every 5 minutes

## Testing the App

### Check if Data is Being Collected
1. Wait 5 minutes after starting collection
2. Pull down to refresh the dashboard
3. Check "Total Samples" counter
4. Verify heart rate is updating

### Export Your Data
1. Tap "Export CSV" button
2. Choose where to share (Gmail, Drive, etc.)
3. Open the CSV file to verify data

## Troubleshooting

### App Won't Install
```bash
# Clean build
flutter clean
flutter pub get
flutter run
```

### No Permissions Dialog
- Go to Settings → Apps → Health Data Collector → Permissions
- Manually grant all permissions

### No Data Appearing
1. Open Health Connect app
2. Verify it has recent data from Samsung Health
3. Manually sync your watch
4. Restart the app

### Background Service Stops
1. Settings → Apps → Health Data Collector
2. Battery → Unrestricted
3. Background data → Allow

## Building Release APK

```bash
# Build release APK
flutter build apk --release

# APK will be at:
# build/app/outputs/flutter-apk/app-release.apk
```

## File Locations

### CSV Files
CSV files are saved to:
```
/data/data/com.healthml.health_data_collector/app_flutter/
```

You can access them via:
- Export button in the app
- Android File Manager (requires root)
- ADB pull command

### Logs
View app logs:
```bash
flutter logs
```

## Common Commands

```bash
# Hot reload (during development)
# Press 'r' in terminal

# Hot restart
# Press 'R' in terminal

# Clear data and restart
flutter clean
flutter run

# Check for issues
flutter analyze

# Run tests
flutter test
```

## Next Steps

1. **Wear your watch** for at least 24 hours to get HRV data
2. **Keep the app running** in the background
3. **Check notifications** to see collection status
4. **Export data regularly** for your ML project

## Support Resources

- [Flutter Documentation](https://docs.flutter.dev/)
- [Health Package Docs](https://pub.dev/packages/health)
- [Health Connect Guide](https://developer.android.com/health-and-fitness/guides/health-connect)
- [Samsung Health SDK](https://developer.samsung.com/health)

## Data Format Reference

Your CSV will look like this:
```csv
Timestamp,DataType,Value,Unit,Source
2026-01-14 20:30:00,HEART_RATE,72,bpm,Samsung Health
2026-01-14 20:30:00,STEPS,5432,steps,Samsung Health
2026-01-14 20:30:00,ACTIVE_ENERGY_BURNED,245.5,kcal,Samsung Health
```

## Performance Tips

1. **Battery Life**: The foreground service uses minimal battery
2. **Storage**: Each day generates ~1-5 MB of CSV data
3. **Sync Frequency**: Data syncs from watch every 15-30 minutes
4. **Collection Interval**: Currently set to 5 minutes (configurable in code)

---

**Ready to start?** Run `flutter run` and begin collecting your health data! 🚀
