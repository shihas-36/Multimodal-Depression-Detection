import os
import django
import time
from django.db import connections
from django.db.utils import OperationalError

# Set the Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Setup Django
django.setup()

from django.contrib.auth import get_user_model

def wait_for_db():
    """Wait for database to be available"""
    print("⏳ Waiting for database...")
    db_conn = None
    attempts = 0
    while not db_conn and attempts < 30:
        try:
            db_conn = connections['default']
            db_conn.cursor()
        except OperationalError:
            attempts += 1
            time.sleep(1)
    
    if not db_conn:
        print("❌ Database unavailable after 30 seconds")
        return False
    print("✅ Database is up!")
    return True

def create_superuser():
    User = get_user_model()

    # Get superuser credentials from environment variables with defaults
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL")

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print(f"✅ Superuser '{username}' created")
    else:
        print(f"⚠️ Superuser '{username}' already exists")

if __name__ == "__main__":
    if wait_for_db():
        create_superuser()
