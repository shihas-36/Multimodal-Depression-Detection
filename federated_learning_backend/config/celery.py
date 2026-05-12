import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Load configuration from Django settings, all config keys will be namespaced and prefixed with CELERY
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'monitor-active-rounds': {
        'task': 'fl_core.tasks.monitor_active_rounds',
        'schedule': 30.0,
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
