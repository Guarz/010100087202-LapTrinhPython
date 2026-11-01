from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def countdown(value):
    """Khoảng thời gian tới `value` bằng tiếng Việt, VD: '1 ngày 23 giờ', '45 phút'."""
    if not value:
        return ''
    seconds = int((value - timezone.now()).total_seconds())
    if seconds <= 0:
        return 'đã quá hạn'
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    if days:
        return f'{days} ngày {hours} giờ' if hours else f'{days} ngày'
    if hours:
        return f'{hours} giờ {minutes} phút' if minutes else f'{hours} giờ'
    return f'{max(minutes, 1)} phút'
