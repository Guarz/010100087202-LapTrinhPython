# planner/risk.py
"""
ĐIỂM RỦI RO TRỄ HẠN (0-100)

Công thức gồm 5 thành phần (tổng tối đa 100 điểm):

1. Áp lực thời gian (tối đa 50): khối lượng còn lại / năng lực học còn lại
   trước deadline. Năng lực = số ngày còn lại x số phút học mỗi ngày,
   nhưng không vượt quá thời gian thực còn lại.
2. Độ gấp (tối đa 20): <= 24h: 20, <= 72h: 12, <= 7 ngày: 6.
3. Mức ưu tiên (tối đa 10): Cao 10, Trung bình 5, Thấp 0.
4. Chưa bắt đầu (tối đa 10): task 'todo' chưa có phút tập trung nào
   khi còn <= 72h.
5. Chưa được xếp lịch (tối đa 10): phần khối lượng còn lại chưa có
   ScheduleBlock nào trước deadline.

Task đã xong -> 0 điểm. Task quá hạn chưa xong -> 100 điểm.
Mức: >= 70 Cao, >= 40 Trung bình, còn lại Thấp.
"""
from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

DEFAULT_DAILY_STUDY_MINUTES = 240

LEVEL_HIGH = 'high'
LEVEL_MEDIUM = 'medium'
LEVEL_LOW = 'low'

LEVEL_LABELS = {
    LEVEL_HIGH: 'Rủi ro cao',
    LEVEL_MEDIUM: 'Rủi ro trung bình',
    LEVEL_LOW: 'Rủi ro thấp',
}


@dataclass
class RiskResult:
    score: int
    level: str
    remaining_minutes: int
    hours_left: float
    reasons: list = field(default_factory=list)

    @property
    def label(self):
        return LEVEL_LABELS[self.level]


def _level_for(score):
    if score >= 70:
        return LEVEL_HIGH
    if score >= 40:
        return LEVEL_MEDIUM
    return LEVEL_LOW


def calculate_risk(
    *,
    hours_left,
    estimated_minutes,
    focused_minutes=0,
    scheduled_minutes=0,
    priority=2,
    status='todo',
    daily_study_minutes=DEFAULT_DAILY_STUDY_MINUTES,
):
    """Hàm thuần (không truy cập DB) để dễ kiểm thử."""
    remaining = max(int(estimated_minutes) - int(focused_minutes), 0)

    if status == 'completed':
        return RiskResult(0, LEVEL_LOW, 0, hours_left, ['Đã hoàn thành.'])

    if hours_left <= 0:
        return RiskResult(
            100, LEVEL_HIGH, remaining, hours_left,
            ['Đã quá hạn nhưng chưa hoàn thành.'],
        )

    if remaining == 0:
        return RiskResult(
            5, LEVEL_LOW, 0, hours_left,
            ['Đã tập trung đủ thời lượng ước tính, chỉ cần đánh dấu hoàn thành.'],
        )

    reasons = []
    minutes_left = hours_left * 60
    capacity = min(
        minutes_left,
        max(daily_study_minutes, hours_left / 24 * daily_study_minutes),
    )

    # 1. Áp lực thời gian
    ratio = remaining / capacity if capacity > 0 else 2
    pressure = min(ratio, 1.0) * 50
    if ratio > 1:
        reasons.append(
            f'Cần {remaining} phút nhưng chỉ còn khoảng {int(capacity)} phút học khả dụng.'
        )
    elif ratio >= 0.5:
        reasons.append(f'Khối lượng còn lại chiếm {int(ratio * 100)}% thời gian học khả dụng.')

    # 2. Độ gấp
    if hours_left <= 24:
        urgency = 20
        reasons.append(f'Còn chưa đến {max(int(hours_left), 1)} giờ tới hạn.')
    elif hours_left <= 72:
        urgency = 12
        reasons.append(f'Còn khoảng {int(hours_left // 24)} ngày tới hạn.')
    elif hours_left <= 168:
        urgency = 6
    else:
        urgency = 0

    # 3. Ưu tiên
    priority_points = {1: 10, 2: 5}.get(priority, 0)

    # 4. Chưa bắt đầu
    not_started = 0
    if status == 'todo' and focused_minutes == 0 and hours_left <= 72:
        not_started = 10
        reasons.append('Chưa bắt đầu học phiên nào cho nhiệm vụ này.')

    # 5. Chưa được xếp lịch
    uncovered = max(remaining - scheduled_minutes, 0) / remaining
    unscheduled = uncovered * 10
    if uncovered >= 0.5:
        reasons.append('Phần lớn khối lượng chưa được xếp vào lịch học.')

    score = round(pressure + urgency + priority_points + not_started + unscheduled)
    score = max(0, min(score, 100))
    return RiskResult(score, _level_for(score), remaining, round(hours_left, 1), reasons)


def assess_task(task, now=None):
    """Thu thập dữ liệu từ DB rồi gọi calculate_risk."""
    from .models import PomodoroLog, ScheduleBlock

    now = now or timezone.now()
    focused_seconds = (
        PomodoroLog.objects
        .filter(task=task, user=task.user)
        .exclude(status='deferred')
        .aggregate(total=Sum('actual_seconds'))['total']
    ) or 0
    focused_minutes = focused_seconds // 60

    scheduled_minutes = 0
    blocks = ScheduleBlock.objects.filter(
        task=task,
        user=task.user,
        end_time__gt=now,
        start_time__lt=task.deadline,
    ).only('start_time', 'end_time')
    for block in blocks:
        start = max(block.start_time, now)
        end = min(block.end_time, task.deadline)
        if end > start:
            scheduled_minutes += int((end - start) / timedelta(minutes=1))

    return calculate_risk(
        hours_left=(task.deadline - now).total_seconds() / 3600,
        estimated_minutes=task.estimated_minutes,
        focused_minutes=focused_minutes,
        scheduled_minutes=scheduled_minutes,
        priority=task.priority,
        status=task.status,
    )


def assess_user_tasks(user, now=None):
    """Trả về danh sách (task, RiskResult) cho task chưa xong, rủi ro cao trước."""
    from .models import Task

    now = now or timezone.now()
    tasks = (
        Task.objects
        .filter(user=user)
        .exclude(status='completed')
        .select_related('course')
    )
    results = [(task, assess_task(task, now)) for task in tasks]
    results.sort(key=lambda item: (-item[1].score, item[0].deadline))
    return results
