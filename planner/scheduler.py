# planner/scheduler.py
"""
THUẬT TOÁN SINH KẾ HOẠCH TUẦN

Đầu vào: Task chưa xong, lịch bận (RecurringSchedule + ScheduleBlock),
khung giờ ngủ trong UserProfile.

1. Sinh khối bận cố định từ RecurringSchedule cho 7 ngày tới.
2. Tính các khoảng trống trong khung giờ thức (compute_free_slots).
3. Sắp xếp Task: ưu tiên (Cao -> Thấp), deadline (gần -> xa),
   thời lượng (dài -> ngắn).
4. First-fit: mỗi Task duyệt các khoảng trống theo thời gian, chia
   thành phiên tối đa 90 phút, nghỉ 10 phút giữa các phiên, phiên
   phải kết thúc trước deadline, không để phần dư < 25 phút và tối đa
   4 giờ học mỗi ngày để rải đều khối lượng (plan_sessions).
5. Lưu các phiên thành ScheduleBlock trạng thái 'suggested'. Người dùng
   có thể kéo thả / sửa; khối đã chỉnh chuyển sang 'confirmed' và được
   giữ lại ở lần sinh lịch sau.

plan_sessions và compute_free_slots là hàm thuần, không truy cập DB.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import RecurringSchedule, ScheduleBlock, Task, UserProfile

MAX_SESSION_MINUTES = 90
MIN_SESSION_MINUTES = 25
BREAK_MINUTES = 10
MAX_DAILY_MINUTES = 240
MIN_FREE_SLOT_MINUTES = 30
PLANNING_DAYS = 7


@dataclass
class PlanTask:
    key: object
    title: str
    minutes: int
    deadline: datetime
    priority: int = 2


@dataclass
class PlannedSession:
    task: PlanTask
    start: datetime
    end: datetime

    @property
    def minutes(self):
        return int((self.end - self.start) / timedelta(minutes=1))


def parse_time_str(t_str):
    """Chuyển chuỗi 'HH:MM' thành datetime.time"""
    parts = t_str.strip().split(':')
    return time(int(parts[0]), int(parts[1]))


def parse_range(value, fallback):
    try:
        start_str, end_str = value.split('-')
        return parse_time_str(start_str), parse_time_str(end_str)
    except (AttributeError, ValueError, IndexError):
        return fallback


def compute_free_slots(busy, start_date, days, wake_time, sleep_time, now,
                       min_minutes=MIN_FREE_SLOT_MINUTES, lead_minutes=15):
    """
    busy: danh sách (start, end) aware datetime.
    Trả về danh sách [start, end] (list để plan_sessions cập nhật tại chỗ).
    """
    tz = timezone.get_current_timezone()
    busy = sorted(busy)
    slots = []

    for offset in range(days + 1):
        day = start_date + timedelta(days=offset)
        day_start = timezone.make_aware(datetime.combine(day, wake_time), tz)
        day_end = timezone.make_aware(datetime.combine(day, sleep_time), tz)
        if day_end <= day_start:
            # Giờ ngủ sau nửa đêm, VD thức 06:00 -> ngủ 01:00 hôm sau
            day_end += timedelta(days=1)

        if now >= day_end:
            continue
        if now > day_start:
            day_start = now + timedelta(minutes=lead_minutes)

        pointer = day_start
        for busy_start, busy_end in busy:
            if busy_end <= pointer or busy_start >= day_end:
                continue
            if busy_start > pointer:
                slots.append([pointer, min(busy_start, day_end)])
            pointer = max(pointer, busy_end)
        if pointer < day_end:
            slots.append([pointer, day_end])

    return [
        slot for slot in slots
        if (slot[1] - slot[0]) >= timedelta(minutes=min_minutes)
    ]


def sort_tasks(tasks):
    return sorted(tasks, key=lambda t: (t.priority, t.deadline, -t.minutes))


def plan_sessions(tasks, free_slots, max_session=MAX_SESSION_MINUTES,
                  min_session=MIN_SESSION_MINUTES, break_minutes=BREAK_MINUTES,
                  max_daily_minutes=MAX_DAILY_MINUTES):
    """
    Xếp các PlanTask vào free_slots (list [start, end], bị cập nhật tại chỗ).
    Mỗi ngày học tối đa max_daily_minutes để rải đều khối lượng.
    Trả về (sessions, unscheduled) với unscheduled = {task.key: phút chưa xếp}.
    """
    sessions = []
    unscheduled = {}
    daily_used = {}

    for task in sort_tasks(tasks):
        remaining = task.minutes
        for slot in free_slots:
            if remaining <= 0:
                break
            while remaining > 0:
                slot_start, slot_end = slot
                day = timezone.localtime(slot_start).date()
                limit_end = min(slot_end, task.deadline)
                available = min(
                    int((limit_end - slot_start) / timedelta(minutes=1)),
                    max_daily_minutes - daily_used.get(day, 0),
                )
                duration = min(remaining, max_session, available)
                # Không để lại phần dư quá ngắn (VD 100 phút -> 75 + 25 thay vì 90 + 10)
                leftover = remaining - duration
                if 0 < leftover < min_session and duration - (min_session - leftover) >= min_session:
                    duration -= min_session - leftover
                if duration <= 0 or duration < min(min_session, remaining):
                    break
                end = slot_start + timedelta(minutes=duration)
                sessions.append(PlannedSession(task, slot_start, end))
                daily_used[day] = daily_used.get(day, 0) + duration
                remaining -= duration
                slot[0] = end + timedelta(minutes=break_minutes)
        if remaining > 0:
            unscheduled[task.key] = remaining

    sessions.sort(key=lambda s: s.start)
    return sessions, unscheduled


def _materialize_recurring(user, start_date, end_date, now):
    tz = timezone.get_current_timezone()
    rules = list(RecurringSchedule.objects.filter(user=user))
    day = start_date
    while day <= end_date:
        for rule in rules:
            if rule.day_of_week != day.weekday():
                continue
            block_start = timezone.make_aware(datetime.combine(day, rule.start_time), tz)
            block_end = timezone.make_aware(datetime.combine(day, rule.end_time), tz)
            if block_end > now:
                ScheduleBlock.objects.get_or_create(
                    user=user,
                    title=f"Lịch cố định: {rule.title}",
                    start_time=block_start,
                    end_time=block_end,
                    is_fixed=True,
                    defaults={'status': 'confirmed'},
                )
        day += timedelta(days=1)


def auto_generate_weekly_schedule(user, now=None):
    """Sinh lịch 7 ngày tới. Trả về số khối lịch gợi ý đã tạo."""
    return generate_weekly_plan(user, now=now)['created']


def generate_weekly_plan(user, now=None):
    now = now or timezone.now()
    start_date = timezone.localtime(now).date()
    end_date = start_date + timedelta(days=PLANNING_DAYS)
    horizon_end = timezone.make_aware(
        datetime.combine(end_date, time(23, 59)),
        timezone.get_current_timezone(),
    )

    profile, _ = UserProfile.objects.get_or_create(user=user)
    sleep_start, wake_time = parse_range(profile.sleep_hours, (time(23, 0), time(6, 0)))

    # Xóa gợi ý cũ chưa xác nhận để sinh lại
    ScheduleBlock.objects.filter(
        user=user, is_fixed=False, status='suggested', start_time__gte=now,
    ).delete()

    _materialize_recurring(user, start_date, end_date, now)

    existing = list(ScheduleBlock.objects.filter(
        user=user, end_time__gt=now, start_time__lt=horizon_end,
    ))
    busy = [(b.start_time, b.end_time) for b in existing]
    free_slots = compute_free_slots(
        busy, start_date, PLANNING_DAYS, wake_time, sleep_start, now,
    )

    # Trừ thời lượng đã có khối lịch xác nhận cho cùng task
    confirmed_minutes = {}
    for block in existing:
        if block.task_id and not block.is_fixed:
            minutes = int((block.end_time - max(block.start_time, now)) / timedelta(minutes=1))
            confirmed_minutes[block.task_id] = confirmed_minutes.get(block.task_id, 0) + minutes

    plan_tasks = []
    for task in Task.objects.filter(
        user=user, status__in=['todo', 'in_progress'], deadline__gt=now,
    ):
        minutes = task.estimated_minutes - confirmed_minutes.get(task.id, 0)
        if minutes > 0:
            plan_tasks.append(PlanTask(task, task.title, minutes, task.deadline, task.priority))

    sessions, unscheduled = plan_sessions(plan_tasks, free_slots)

    ScheduleBlock.objects.bulk_create([
        ScheduleBlock(
            user=user,
            task=session.task.key,
            title=f"Ôn tập: {session.task.title}",
            start_time=session.start,
            end_time=session.end,
            is_fixed=False,
            status='suggested',
        )
        for session in sessions
    ])

    return {
        'created': len(sessions),
        'unscheduled': {task.title: minutes for task, minutes in unscheduled.items()},
    }
