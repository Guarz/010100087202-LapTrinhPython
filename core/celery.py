"""
Celery app cho background jobs (nhắc deadline định kỳ).

Chạy worker + beat (cần REDIS_URL):
    celery -A core worker -B -l info
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
