# planner/calendar_invites.py
"""
LỜI MỜI LỊCH QUA EMAIL (iCalendar iTIP, RFC 5546)

Khi người dùng bật "Gửi lời mời lịch" trong Hồ sơ, mỗi deadline (Task) và
phiên học đã xác nhận (ScheduleBlock không cố định, status='confirmed') được
gửi tới email đã xác thực dưới dạng lời mời lịch:

- Tạo mới / sửa  -> METHOD:REQUEST, cùng UID, SEQUENCE tăng dần nên Gmail,
  Outlook, Apple Calendar cập nhật đúng sự kiện cũ thay vì tạo bản trùng.
- Xóa / hoàn thành / hủy xác nhận -> METHOD:CANCEL (STATUS:CANCELLED).

Email gồm phần text/calendar; method=REQUEST (để ứng dụng mail nhận diện là
lời mời) và tệp đính kèm invite.ics. Việc gửi chạy trong Celery task để
người dùng không phải chờ khi lưu.

Chỉ gửi lại khi nội dung đổi: invite_hash lưu dấu vân tay nội dung đã gửi.
"""
import hashlib
from datetime import timedelta
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .icalendar import _escape_text, _fold_line, _format_datetime
from .models import ScheduleBlock, Task, UserProfile

KIND_TASK = 'task'
KIND_BLOCK = 'block'
CANCELLED_HASH = 'cancelled'
PRODID = '-//StudyPlanner//Calendar Invite//VI'

MODELS = {KIND_TASK: Task, KIND_BLOCK: ScheduleBlock}


def invite_uid(kind, pk):
    return f'invite-{kind}-{pk}@studyplanner'


def can_receive_invites(user):
    profile = UserProfile.objects.filter(user=user).first()
    return bool(
        user.email
        and profile
        and profile.calendar_invites_enabled
        and profile.email_verified
    )


def is_tracked_block(block):
    """Chỉ phiên học do người dùng tạo hoặc đã xác nhận, không gửi lịch bận cố định / gợi ý."""
    return not block.is_fixed and block.status == 'confirmed'


def event_data(obj, kind):
    """Nội dung sự kiện cần có trên lịch, hoặc None nếu sự kiện nên bị hủy."""
    if kind == KIND_TASK:
        if obj.status == 'completed':
            return None
        description = [
            f'Ưu tiên: {obj.get_priority_display()}',
            f'Thời lượng ước tính: {obj.estimated_minutes} phút',
        ]
        if obj.course_id:
            description.append(f'Môn: {obj.course.code} · {obj.course.name}')
        elif obj.subject_name:
            description.append(f'Môn: {obj.subject_name}')
        if obj.material_url:
            description.append(f'Tài liệu: {obj.material_url}')
        return {
            'summary': f'Deadline: {obj.title}',
            'start': obj.deadline,
            'end': obj.deadline + timedelta(minutes=15),
            'description': '\n'.join(description),
            'transparent': True,  # deadline không chiếm thời gian rảnh
        }

    if not is_tracked_block(obj):
        return None
    description = ['Phiên học trong kế hoạch StudyPlanner']
    if obj.task_id:
        description.append(f'Nhiệm vụ: {obj.task.title}')
    return {
        'summary': obj.title,
        'start': obj.start_time,
        'end': obj.end_time,
        'description': '\n'.join(description),
        'transparent': False,
    }


def fingerprint(data):
    raw = '|'.join([
        data['summary'],
        _format_datetime(data['start']),
        _format_datetime(data['end']),
        data['description'],
    ])
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _param(value):
    """Giá trị tham số iCalendar (VD: CN) phải đặt trong ngoặc kép nếu có , ; :"""
    return '"' + str(value).replace('"', "'") + '"'


def build_invite_ics(method, uid, sequence, data, organizer_email, attendee_email, attendee_name=''):
    cancelled = method == 'CANCEL'
    lines = [
        'BEGIN:VCALENDAR',
        f'PRODID:{PRODID}',
        'VERSION:2.0',
        'CALSCALE:GREGORIAN',
        f'METHOD:{method}',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'SEQUENCE:{sequence}',
        f'DTSTAMP:{_format_datetime(timezone.now())}',
        f'DTSTART:{_format_datetime(data["start"])}',
        f'DTEND:{_format_datetime(data["end"])}',
        f'SUMMARY:{_escape_text(data["summary"])}',
        f'DESCRIPTION:{_escape_text(data["description"])}',
        f'STATUS:{"CANCELLED" if cancelled else "CONFIRMED"}',
        f'TRANSP:{"TRANSPARENT" if data["transparent"] else "OPAQUE"}',
        f'ORGANIZER;CN=StudyPlanner:mailto:{organizer_email}',
        f'ATTENDEE;CN={_param(attendee_name or attendee_email)};ROLE=REQ-PARTICIPANT;'
        f'PARTSTAT=ACCEPTED;RSVP=FALSE:mailto:{attendee_email}',
    ]
    if not cancelled:
        # Nhắc trước 1 giờ (ứng dụng lịch hiện thông báo)
        lines += [
            'BEGIN:VALARM',
            'ACTION:DISPLAY',
            f'DESCRIPTION:{_escape_text(data["summary"])}',
            'TRIGGER:-PT1H',
            'END:VALARM',
        ]
    lines += ['END:VEVENT', 'END:VCALENDAR']
    return '\r\n'.join(part for line in lines for part in _fold_line(line)) + '\r\n'


def send_invite(user, method, uid, sequence, data, is_update=False):
    organizer = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
    ics = build_invite_ics(
        method, uid, sequence, data,
        organizer_email=organizer,
        attendee_email=user.email,
        attendee_name=user.get_full_name() or user.username,
    )
    when = timezone.localtime(data['start']).strftime('%H:%M %d/%m/%Y')
    if method == 'CANCEL':
        subject = f'Đã hủy: {data["summary"]}'
        intro = 'Sự kiện sau đã được xóa, hoàn thành hoặc hủy trong StudyPlanner:'
    elif is_update:
        subject = f'Cập nhật lịch: {data["summary"]} ({when})'
        intro = 'Sự kiện trong lịch của bạn vừa được cập nhật:'
    else:
        subject = f'Lời mời lịch: {data["summary"]} ({when})'
        intro = 'StudyPlanner đã thêm sự kiện sau vào lịch của bạn:'

    body = (
        f'Xin chào {user.username},\n\n{intro}\n\n'
        f'{data["summary"]}\nThời gian: {when}\n{data["description"]}\n\n'
        'Mở tệp invite.ics hoặc bấm "Thêm vào lịch" trong ứng dụng email để đồng bộ.\n'
        'Tắt lời mời lịch trong trang Hồ sơ của StudyPlanner.\n'
    )
    message = EmailMultiAlternatives(subject=subject, body=body, to=[user.email])
    message.attach_alternative(ics, f'text/calendar; method={method}')
    message.attach('invite.ics', ics, 'application/ics')
    message.send()


def sync_invite(kind, pk):
    """Gửi REQUEST/CANCEL cho một Task hoặc ScheduleBlock nếu cần. Trả về kết quả dạng chuỗi."""
    model = MODELS[kind]
    obj = model.objects.select_related('user').filter(pk=pk).first()
    if obj is None:
        return 'missing'
    user = obj.user
    if not can_receive_invites(user):
        return 'disabled'

    data = event_data(obj, kind)
    uid = invite_uid(kind, obj.pk)

    if data is None:
        if obj.invite_sequence is None or obj.invite_hash == CANCELLED_HASH:
            return 'skip'
        sequence = obj.invite_sequence + 1
        cancel_data = _cancel_data(obj, kind)
        send_invite(user, 'CANCEL', uid, sequence, cancel_data)
        model.objects.filter(pk=obj.pk).update(invite_sequence=sequence, invite_hash=CANCELLED_HASH)
        return 'cancelled'

    new_hash = fingerprint(data)
    if new_hash == obj.invite_hash:
        return 'unchanged'
    if obj.invite_sequence is None and data['end'] < timezone.now():
        return 'past'

    is_update = obj.invite_sequence is not None
    sequence = obj.invite_sequence + 1 if is_update else 0
    send_invite(user, 'REQUEST', uid, sequence, data, is_update=is_update)
    model.objects.filter(pk=obj.pk).update(invite_sequence=sequence, invite_hash=new_hash)
    return 'updated' if is_update else 'sent'


def _cancel_data(obj, kind):
    if kind == KIND_TASK:
        return {
            'summary': f'Deadline: {obj.title}',
            'start': obj.deadline,
            'end': obj.deadline + timedelta(minutes=15),
            'description': '',
            'transparent': True,
        }
    return {
        'summary': obj.title,
        'start': obj.start_time,
        'end': obj.end_time,
        'description': '',
        'transparent': False,
    }


def snapshot_for_cancel(obj, kind):
    """Dữ liệu cần để gửi CANCEL sau khi bản ghi đã bị xóa (kiểu JSON cho Celery)."""
    data = _cancel_data(obj, kind)
    return {
        'user_id': obj.user_id,
        'uid': invite_uid(kind, obj.pk),
        'sequence': obj.invite_sequence + 1,
        'summary': data['summary'],
        'start': data['start'].isoformat(),
        'end': data['end'].isoformat(),
        'transparent': data['transparent'],
    }


def send_cancel_from_snapshot(snapshot):
    from datetime import datetime
    from django.contrib.auth.models import User

    user = User.objects.filter(pk=snapshot['user_id']).first()
    if user is None or not can_receive_invites(user):
        return 'disabled'
    data = {
        'summary': snapshot['summary'],
        'start': datetime.fromisoformat(snapshot['start']),
        'end': datetime.fromisoformat(snapshot['end']),
        'description': '',
        'transparent': snapshot['transparent'],
    }
    send_invite(user, 'CANCEL', snapshot['uid'], snapshot['sequence'], data)
    return 'cancelled'


def upcoming_items(user, days=60):
    """Deadline và phiên học sắp tới để gửi lời mời khi người dùng vừa bật tính năng."""
    now = timezone.now()
    horizon = now + timedelta(days=days)
    tasks = Task.objects.filter(
        user=user, deadline__gt=now, deadline__lte=horizon,
    ).exclude(status='completed').values_list('pk', flat=True)
    blocks = ScheduleBlock.objects.filter(
        user=user, is_fixed=False, status='confirmed', end_time__gt=now, start_time__lte=horizon,
    ).values_list('pk', flat=True)
    return [(KIND_TASK, pk) for pk in tasks] + [(KIND_BLOCK, pk) for pk in blocks]
