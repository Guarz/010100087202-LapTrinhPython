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


# ------------------------------------------------------------
# Lời mời lịch qua email (planner/calendar_invites.py)
# ------------------------------------------------------------

@shared_task(autoretry_for=(OSError,), retry_backoff=30, max_retries=3)
def sync_calendar_invite_task(kind, pk):
    from .calendar_invites import sync_invite
    return sync_invite(kind, pk)


@shared_task(autoretry_for=(OSError,), retry_backoff=30, max_retries=3)
def cancel_calendar_invite_task(snapshot):
    from .calendar_invites import send_cancel_from_snapshot
    return send_cancel_from_snapshot(snapshot)


@shared_task
def send_all_calendar_invites_task(user_id):
    """Gửi lời mời cho mọi deadline / phiên học sắp tới khi người dùng vừa bật tính năng."""
    from django.contrib.auth.models import User
    from .calendar_invites import sync_invite, upcoming_items

    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return 0
    return sum(sync_invite(kind, pk) in ('sent', 'updated') for kind, pk in upcoming_items(user))
