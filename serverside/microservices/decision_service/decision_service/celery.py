import os
from celery import Celery



os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'decision_service.settings')

app = Celery('decision_service')
app.conf.enable_utc = True
app.conf.timezone = 'Africa/Johannesburg'
# Using a string here means the worker doesn't have to serialize
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks (Decision + Generator tasks when Generator is installed).
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
