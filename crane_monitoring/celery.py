import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crane_monitoring.settings')

app = Celery('crane_monitoring')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()