from datetime import timedelta, timezone as datetime_timezone

from django.utils import timezone

from .models import ScheduleBlock, Task


def _escape_text(value):
    return (
        str(value)
        .replace('\\', '\\\\')
        .replace('\r\n', '\n')
        .replace('\r', '\n')
        .replace('\n', '\\n')
        .replace(';', '\\;')
        .replace(',', '\\,')
    )


def _fold_line(line, limit=75):
    lines = []
    current = ''
    current_bytes = 0

    for character in line:
        character_bytes = len(character.encode('utf-8'))
        if current_bytes + character_bytes > limit:
            lines.append(current)
            current = ' '
            current_bytes = 1
        current += character
        current_bytes += character_bytes

    lines.append(current)
    return lines


def _format_datetime(value):
    return value.astimezone(datetime_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def build_user_calendar(user):
    now = timezone.now()
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//AI Study Planner//Calendar Export//VI',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:AI Study Planner',
    ]

    tasks = (
        Task.objects
        .filter(user=user)
        .select_related('course')
        .order_by('deadline', 'pk')
    )
    for task in tasks:
        description = [
            f'Trạng thái: {task.get_status_display()}',
            f'Ưu tiên: {task.get_priority_display()}',
            f'Thời lượng ước tính: {task.estimated_minutes} phút',
        ]
        if task.course:
            description.append(f'Khóa học: {task.course.name}')
        elif task.subject_name:
            description.append(f'Môn học: {task.subject_name}')
        if task.material_url:
            description.append(f'Tài liệu: {task.material_url}')

        start = task.deadline
        end = start + timedelta(minutes=15)
        lines.extend([
            'BEGIN:VEVENT',
            f'UID:task-{task.pk}@ai-study-planner.local',
            f'DTSTAMP:{_format_datetime(now)}',
            f'DTSTART:{_format_datetime(start)}',
            f'DTEND:{_format_datetime(end)}',
            f'SUMMARY:{_escape_text(f"Deadline: {task.title}")}',
            f'DESCRIPTION:{_escape_text(chr(10).join(description))}',
            'END:VEVENT',
        ])

    blocks = (
        ScheduleBlock.objects
        .filter(user=user)
        .select_related('task')
        .order_by('start_time', 'pk')
    )
    for block in blocks:
        description = [f'Trạng thái: {block.get_status_display()}']
        if block.task:
            description.append(f'Nhiệm vụ: {block.task.title}')
        if block.is_fixed:
            description.append('Sự kiện lịch cố định')

        lines.extend([
            'BEGIN:VEVENT',
            f'UID:schedule-block-{block.pk}@ai-study-planner.local',
            f'DTSTAMP:{_format_datetime(now)}',
            f'DTSTART:{_format_datetime(block.start_time)}',
            f'DTEND:{_format_datetime(block.end_time)}',
            f'SUMMARY:{_escape_text(block.title)}',
            f'DESCRIPTION:{_escape_text(chr(10).join(description))}',
            'END:VEVENT',
        ])

    lines.append('END:VCALENDAR')
    folded_lines = [
        physical_line
        for line in lines
        for physical_line in _fold_line(line)
    ]
    return '\r\n'.join(folded_lines) + '\r\n'


# ============================================================
# NHẬP LỊCH .ICS (Google Calendar, Outlook, lịch trường...)
# Mỗi VEVENT có DTSTART/DTEND thành một ScheduleBlock cố định
# (lịch bận) để thuật toán xếp lịch tránh các khung giờ này.
# ============================================================

def _unfold(text):
    return text.replace('\r\n', '\n').replace('\n ', '').replace('\n\t', '').split('\n')


def _unescape_text(value):
    return (
        value.replace('\\n', '\n').replace('\\N', '\n')
        .replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\')
    )


def _parse_ics_datetime(value, params):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    value = value.strip()
    if 'VALUE=DATE' in params or len(value) == 8:
        parsed = datetime.strptime(value[:8], '%Y%m%d')
        return timezone.make_aware(parsed), True
    if value.endswith('Z'):
        parsed = datetime.strptime(value, '%Y%m%dT%H%M%SZ')
        return parsed.replace(tzinfo=datetime_timezone.utc), False
    parsed = datetime.strptime(value[:15], '%Y%m%dT%H%M%S')
    tzid = next((p.split('=', 1)[1] for p in params if p.startswith('TZID=')), None)
    if tzid:
        try:
            return parsed.replace(tzinfo=ZoneInfo(tzid)), False
        except Exception:  # noqa: BLE001 - TZID lạ thì dùng múi giờ hệ thống
            pass
    return timezone.make_aware(parsed), False


def parse_ics_events(text):
    """Trả về danh sách dict {uid, title, start, end} từ nội dung .ics."""
    events = []
    current = None
    for line in _unfold(text):
        if line == 'BEGIN:VEVENT':
            current = {}
            continue
        if line == 'END:VEVENT':
            if current and current.get('start'):
                start = current['start']
                end = current.get('end') or (
                    start + timedelta(days=1) if current.get('all_day') else start + timedelta(hours=1)
                )
                if end > start:
                    events.append({
                        'uid': current.get('uid', ''),
                        'title': current.get('title') or 'Sự kiện nhập',
                        'start': start,
                        'end': end,
                    })
            current = None
            continue
        if current is None or ':' not in line:
            continue
        key_part, value = line.split(':', 1)
        name, *params = key_part.split(';')
        name = name.upper()
        try:
            if name == 'DTSTART':
                current['start'], current['all_day'] = _parse_ics_datetime(value, params)
            elif name == 'DTEND':
                current['end'], _ = _parse_ics_datetime(value, params)
        except ValueError:
            continue
        if name == 'SUMMARY':
            current['title'] = _unescape_text(value)[:180]
        elif name == 'UID':
            current['uid'] = value
    return events


def import_ics_for_user(user, text):
    """Nhập sự kiện .ics thành khối lịch bận cố định. Bỏ qua sự kiện đã qua và bản trùng."""
    now = timezone.now()
    created = 0
    for event in parse_ics_events(text):
        if event['end'] <= now:
            continue
        title = f"Lịch nhập: {event['title']}"
        _, was_created = ScheduleBlock.objects.get_or_create(
            user=user,
            title=title,
            start_time=event['start'],
            end_time=event['end'],
            defaults={'is_fixed': True, 'status': 'confirmed'},
        )
        created += int(was_created)
    return created
