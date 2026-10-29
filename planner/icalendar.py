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
