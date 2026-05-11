#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from fl_core.models import Round, ModelVersion, Device, DeviceToken

print("=== ModelVersions ===")
for mv in ModelVersion.objects.all():
    print(f"  ID: {mv.id}, Version: {mv.version}, Active: {mv.is_active}")

print("\n=== Rounds ===")
for r in Round.objects.all():
    print(f"  ID: {r.id}, Round #: {r.round_number}, Status: {r.status}, Model V: {r.model_version.version if r.model_version else 'None'}")

print("\n=== Devices ===")
for d in Device.objects.all():
    has_token = hasattr(d, 'token') and d.token
    print(f"  ID: {d.id}, Name: {d.device_name}, Has Token: {has_token}")

print("\n=== DeviceTokens ===")
for dt in DeviceToken.objects.all():
    print(f"  Device: {dt.device.device_name}, Expired: {dt.is_expired()}, Active: {dt.is_active}")
    print(f"  Token: {dt.token[:20]}...")
    
# Also print a simple command to test API
if DeviceToken.objects.exists():
    token = DeviceToken.objects.first().token
    print(f"\n📝 To test the API, use this token:")
    print(f"TOKEN={token}")
