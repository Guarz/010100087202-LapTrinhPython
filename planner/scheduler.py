# planner/scheduler.py
from datetime import datetime, date, time, timedelta
from django.utils import timezone
from .models import Task, ScheduleBlock, RecurringSchedule, UserProfile


def parse_time_str(t_str):
    """Chuyển chuỗi 'HH:MM' thành datetime.time"""
    parts = t_str.strip().split(':')
    return time(int(parts[0]), int(parts[1]))


def auto_generate_weekly_schedule(user):
    """
    Thuật toán Heuristic xếp lịch tự động cho 7 ngày tới:
    1. Lấy thông tin giờ ngủ cố định (Hard constraint) và khung giờ ưu tiên.
    2. Nhân bản các RecurringSchedule trong tuần thành các khung bận cố định.
    3. Xác định các khoảng thời gian trống khả dụng (Free Time Slots).
    4. Sắp xếp Task theo: Priority (Cao -> Thấp) và Deadline (Gần -> Xa).
    5. Chia nhỏ Task và điền vào các slot trống.
    """
    now = timezone.now()
    start_date = now.date()
    end_date = start_date + timedelta(days=7)

    # 1. Lấy cấu hình UserProfile (giờ ngủ, giờ ưu tiên)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    try:
        sleep_start_str, sleep_end_str = profile.sleep_hours.split('-')
        sleep_start_time = parse_time_str(sleep_start_str)
        sleep_end_time = parse_time_str(sleep_end_str)
    except Exception:
        sleep_start_time = time(23, 0)
        sleep_end_time = time(6, 0)

    # Xóa các gợi ý cũ chưa xác nhận để sinh lại bộ lịch mới
    ScheduleBlock.objects.filter(
        user=user,
        is_fixed=False,
        status='suggested',
        start_time__gte=now
    ).delete()

    # 2. Sinh các khối bận cố định từ RecurringSchedule vào ScheduleBlock (nếu chưa có)
    recurring_rules = RecurringSchedule.objects.filter(user=user)
    current_d = start_date
    while current_d <= end_date:
        weekday = current_d.weekday()  # 0: Thứ 2 ... 6: Chủ nhật
        for rule in recurring_rules:
            if rule.day_of_week == weekday:
                block_start = timezone.make_aware(datetime.combine(current_d, rule.start_time))
                block_end = timezone.make_aware(datetime.combine(current_d, rule.end_time))

                if block_end > now:
                    ScheduleBlock.objects.get_or_create(
                        user=user,
                        title=f"Lịch cố định: {rule.title}",
                        start_time=block_start,
                        end_time=block_end,
                        is_fixed=True,
                        defaults={'status': 'confirmed'}
                    )
        current_d += timedelta(days=1)

    # 3. Quét tất cả các khoảng thời gian bận hiện tại trong 7 ngày tới
    existing_blocks = list(ScheduleBlock.objects.filter(
        user=user,
        start_time__gte=now,
        end_time__lte=timezone.make_aware(datetime.combine(end_date, time(23, 59)))
    ).order_by('start_time'))

    # 4. Tìm các khoảng trống (Free Slots) có độ dài >= 45 phút trong khung thức
    free_slots = []
    current_day = start_date
    while current_day <= end_date:
        # Giả định khung thức: từ sleep_end_time đến sleep_start_time trong ngày
        day_wake_start = timezone.make_aware(datetime.combine(current_day, sleep_end_time))
        day_sleep_start = timezone.make_aware(datetime.combine(current_day, sleep_start_time))

        # Nếu đang xét hôm nay và giờ hiện tại đã trễ hơn giờ thức dậy
        if current_day == start_date and now > day_wake_start:
            day_wake_start = now + timedelta(minutes=15)  # Nghỉ 15p rồi mới bắt đầu

        # Lọc các block bận diễn ra trong ngày hôm nay
        day_busy = [b for b in existing_blocks if b.start_time < day_sleep_start and b.end_time > day_wake_start]
        day_busy.sort(key=lambda x: x.start_time)

        pointer = day_wake_start
        for b in day_busy:
            if b.start_time > pointer:
                gap_minutes = (b.start_time - pointer).total_seconds() / 60
                if gap_minutes >= 45:  # Chỉ lấy slot trống từ 45 phút trở lên
                    free_slots.append({'start': pointer, 'end': b.start_time, 'minutes': gap_minutes})
            pointer = max(pointer, b.end_time)

        if pointer < day_sleep_start:
            gap_minutes = (day_sleep_start - pointer).total_seconds() / 60
            if gap_minutes >= 45:
                free_slots.append({'start': pointer, 'end': day_sleep_start, 'minutes': gap_minutes})

        current_day += timedelta(days=1)

    # 5. Lấy danh sách Task cần làm: sắp xếp theo priority (1 trước), deadline (sớm trước)
    pending_tasks = list(Task.objects.filter(
        user=user,
        status__in=['todo', 'in_progress'],
        deadline__gt=now
    ).order_by('priority', 'deadline'))

    # 6. Heuristic Placement: Phân bổ từng Task vào các Free Slots
    blocks_created = 0
    slot_idx = 0

    for task in pending_tasks:
        remaining_time = task.estimated_minutes

        while remaining_time > 0 and slot_idx < len(free_slots):
            current_slot = free_slots[slot_idx]

            # Nếu slot này bắt đầu sau deadline của task thì không xếp được vào đây
            if current_slot['start'] >= task.deadline:
                break

            # Mỗi phiên học chia nhỏ tối đa 90 phút để tránh quá tải não bộ
            session_duration = min(remaining_time, current_slot['minutes'], 90)

            session_start = current_slot['start']
            session_end = session_start + timedelta(minutes=session_duration)

            # Tạo khối ScheduleBlock gợi ý
            ScheduleBlock.objects.create(
                user=user,
                task=task,
                title=f"Ôn tập: {task.title}",
                start_time=session_start,
                end_time=session_end,
                is_fixed=False,
                status='suggested'
            )
            blocks_created += 1
            remaining_time -= session_duration

            # Cập nhật lại slot trống vừa dùng
            current_slot['start'] = session_end + timedelta(minutes=10)  # 10 phút giải lao
            current_slot['minutes'] = (current_slot['end'] - current_slot['start']).total_seconds() / 60

            if current_slot['minutes'] < 30:  # Nếu slot còn lại dưới 30 phút thì chuyển sang slot tiếp theo
                slot_idx += 1

    return blocks_created