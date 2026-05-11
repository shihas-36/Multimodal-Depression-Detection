#!/bin/sh

echo "Starting service: $SERVICE"

if [ "$SERVICE" = "web" ]; then
    python manage.py migrate
    python manage.py collectstatic --noinput
    gunicorn config.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 2 \
    --timeout 300 \
    --log-level debug \
    --access-logfile - \
    --error-logfile -
elif [ "$SERVICE" = "worker" ]; then
    celery -A config worker -l info --concurrency=1

elif [ "$SERVICE" = "beat" ]; then
    celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

else
    echo "Unknown SERVICE: $SERVICE"
    exit 1
fi