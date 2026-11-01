# planner/context_processors.py
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Task


def upcoming_deadlines(request):
    """Nhắc trong ứng dụng: deadline sắp tới và quá hạn cho thanh điều hướng."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    now = timezone.now()
    open_tasks = Task.objects.filter(user=user).exclude(status='completed')
    upcoming = list(
        open_tasks
        .filter(deadline__gt=now, deadline__lte=now + timedelta(hours=settings.REMINDER_HOURS_BEFORE))
        .order_by('deadline')[:5]
    )
    overdue_count = open_tasks.filter(deadline__lte=now).count()
    return {
        'reminder_tasks': upcoming,
        'reminder_overdue_count': overdue_count,
        'reminder_count': len(upcoming) + overdue_count,
        'reminder_hours': settings.REMINDER_HOURS_BEFORE,
    }
