# planner/tasks.py
"""Celery tasks. Beat lịch trong settings.CELERY_BEAT_SCHEDULE."""
from io import StringIO

from celery import shared_task
from django.conf import settings
from django.core.management import call_command


@shared_task
def send_deadline_reminders_task(hours_before=None):
    output = StringIO()
    call_command(
        'send_deadline_reminders',
        hours_before=hours_before or settings.REMINDER_HOURS_BEFORE,
        stdout=output,
    )
    return output.getvalue()
