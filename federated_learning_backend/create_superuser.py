import os
import django
import time
from django.db import connections
from django.db.utils import OperationalError, ProgrammingError

# Set the Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Setup Django
django.setup()

from django.contrib.auth import get_user_model

def wait_for_db():
    """Wait for database to be available and migrations to be ready"""
    print("⏳ Waiting for database connection...")
    db_conn = None
    attempts = 0
    while not db_conn and attempts < 30:
        try:
            db_conn = connections['default']
            db_conn.cursor()
        except OperationalError:
            attempts += 1
            print(f"   Retry {attempts}/30: Database not reachable yet...")
            time.sleep(2)
    
    if not db_conn:
        print("❌ Database unavailable after 60 seconds")
        return False
    print("✅ Database connection established!")
    return True

def create_superuser():
    User = get_user_model()

    # Get superuser credentials from environment variables with defaults
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Admin123456")
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")

    try:
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            print(f"✅ Superuser '{username}' created successfully")
        else:
            print(f"⚠️ Superuser '{username}' already exists")
    except ProgrammingError as e:
        print(f"⚠️ Could not create superuser: {e}")
        print("   TIP: Ensure 'python manage.py migrate' has run successfully.")
    except Exception as e:
        print(f"❌ Unexpected error creating superuser: {e}")

if __name__ == "__main__":
    if wait_for_db():
        # Small delay to ensure DB is fully ready for queries
        time.sleep(1)
        create_superuser()
