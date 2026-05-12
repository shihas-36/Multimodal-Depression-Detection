import os
import django
import time
from django.db import connections
<<<<<<< HEAD
from django.db.utils import OperationalError, ProgrammingError
=======
from django.db.utils import OperationalError
>>>>>>> fe0cafccb6b8ad0f6dddee5ffb603c1b07fe6f19

# Set the Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Setup Django
django.setup()

from django.contrib.auth import get_user_model

def wait_for_db():
<<<<<<< HEAD
    """Wait for database to be available and migrations to be ready"""
    print("⏳ Waiting for database connection...")
=======
    """Wait for database to be available"""
    print("⏳ Waiting for database...")
>>>>>>> fe0cafccb6b8ad0f6dddee5ffb603c1b07fe6f19
    db_conn = None
    attempts = 0
    while not db_conn and attempts < 30:
        try:
            db_conn = connections['default']
            db_conn.cursor()
        except OperationalError:
            attempts += 1
<<<<<<< HEAD
            print(f"   Retry {attempts}/30: Database not reachable yet...")
            time.sleep(2)
    
    if not db_conn:
        print("❌ Database unavailable after 60 seconds")
        return False
    print("✅ Database connection established!")
=======
            time.sleep(1)
    
    if not db_conn:
        print("❌ Database unavailable after 30 seconds")
        return False
    print("✅ Database is up!")
>>>>>>> fe0cafccb6b8ad0f6dddee5ffb603c1b07fe6f19
    return True

def create_superuser():
    User = get_user_model()

    # Get superuser credentials from environment variables with defaults
<<<<<<< HEAD
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
=======
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
>>>>>>> fe0cafccb6b8ad0f6dddee5ffb603c1b07fe6f19
        create_superuser()
