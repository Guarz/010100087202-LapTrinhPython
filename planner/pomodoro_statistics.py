
# ============================================================
# AI STUDYPLANNER - POMODORO WORKSPACE 2.0
#
# C3.1 - STATISTICS SERVICE V1
#
# Chức năng:
# - Tổng thời gian tập trung
# - Tổng số phiên hoàn thành
# - Chuỗi ngày tập trung
# - Thống kê theo ngày cho Heatmap ở C4
#
# Quy tắc:
# - Chỉ tính phiên hoàn thành.
# - Không tính phiên Gác lại.
# - Hỗ trợ PomodoroLog từ model cũ.
# - Sử dụng múi giờ Việt Nam.
# - Chỉ lấy dữ liệu thuộc user hiện tại.
#
# Không thay đổi hoặc ghi dữ liệu vào database.
# ============================================================

from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from .models import PomodoroLog


# ============================================================
# 01. CONFIGURATION
# ============================================================

VIETNAM_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


# ============================================================
# 02. COMPLETED SESSIONS
# ============================================================

def get_completed_logs(user):
    """
    Lấy các phiên hoàn thành của một người dùng.

    Dữ liệu mới:
        status = 'completed'

    Dữ liệu cũ:
        status IS NULL
        completed = True

    Không lấy phiên deferred.
    """

    return (
        PomodoroLog.objects
        .filter(user=user)
        .filter(
            Q(status="completed") |
            Q(status__isnull=True, completed=True)
        )
        .order_by("start_time", "id")
    )


# ============================================================
# 03. ACTUAL FOCUS SECONDS
# ============================================================

def get_focus_seconds(log):
    """
    Trả về tổng giây tập trung của một phiên.

    Ưu tiên:
        actual_seconds

    Dữ liệu cũ chưa có actual_seconds:
        duration_minutes * 60
    """

    if log.actual_seconds is not None:
        return max(0, log.actual_seconds)

    return max(
        0,
        log.duration_minutes * 60
    )


# ============================================================
# 04. COMPLETION DATE
# ============================================================

def get_completion_date(log):
    """
    Ngày hoàn thành theo múi giờ Việt Nam.

    Phiên mới:
        ưu tiên ended_at.

    Phiên cũ:
        sử dụng start_time.
    """

    completed_at = (
        log.ended_at
        if log.ended_at is not None
        else log.start_time
    )

    if timezone.is_aware(completed_at):
        completed_at = timezone.localtime(
            completed_at,
            VIETNAM_TIMEZONE
        )

    return completed_at.date()


# ============================================================
# 05. DAILY STATISTICS
# ============================================================

def get_daily_focus_seconds(user):
    """
    Tổng hợp giây tập trung theo từng ngày.

    Ví dụ:
    {
        date(2026, 10, 14): 1500,
        date(2026, 10, 15): 3600
    }

    Không cộng phiên Gác lại.
    """

    daily_seconds = {}

    logs = get_completed_logs(user)

    for log in logs:

        study_date = get_completion_date(log)

        focus_seconds = get_focus_seconds(log)

        daily_seconds[study_date] = (
            daily_seconds.get(study_date, 0)
            + focus_seconds
        )

    return daily_seconds


# ============================================================
# 06. CURRENT STREAK
# ============================================================

def calculate_current_streak(daily_seconds):
    """
    Tính chuỗi ngày tập trung hiện tại.

    Quy tắc:
    - Một ngày có hoạt động nếu hoàn thành
      ít nhất một phiên có thời gian > 0.

    - Nếu hôm nay có hoạt động:
        tính chuỗi ngược từ hôm nay.

    - Nếu hôm nay chưa có nhưng hôm qua có:
        tính chuỗi ngược từ hôm qua.

    - Nếu cả hai ngày không có:
        streak = 0.
    """

    today = timezone.now().astimezone(
        VIETNAM_TIMEZONE
    ).date()

    yesterday = today - timedelta(days=1)

    if daily_seconds.get(today, 0) > 0:

        current_day = today

    elif daily_seconds.get(yesterday, 0) > 0:

        current_day = yesterday

    else:

        return 0

    streak = 0

    while daily_seconds.get(current_day, 0) > 0:

        streak += 1

        current_day -= timedelta(days=1)

    return streak


# ============================================================
# 07. MAIN STATISTICS SERVICE
# ============================================================

def get_pomodoro_statistics(user):
    """
    Tạo dữ liệu tổng quan cho Dashboard.

    Ví dụ:
    {
        "total_minutes": 76,
        "completed_sessions": 4,
        "current_streak": 2
    }

    total_minutes sử dụng phút nguyên.
    Phần giây lẻ vẫn được giữ trong
    total_seconds để phục vụ API mở rộng.
    """

    daily_seconds = get_daily_focus_seconds(user)

    total_seconds = sum(
        daily_seconds.values()
    )

    completed_sessions = (
        get_completed_logs(user).count()
    )

    current_streak = calculate_current_streak(
        daily_seconds
    )

    return {
        "total_minutes": total_seconds // 60,
        "total_seconds": total_seconds,
        "completed_sessions": completed_sessions,
        "current_streak": current_streak,
    }


# ============================================================
# 08. DAILY DATA FOR HEATMAP - C4 READY
# ============================================================

def get_pomodoro_daily_data(user):
    """
    Dữ liệu theo ngày dùng cho Heatmap V2.3.

    Kết quả:
    [
        {
            "date": "2026-10-14",
            "minutes": 25.0
        },
        {
            "date": "2026-10-15",
            "minutes": 60.0
        }
    ]

    Không tự tạo dữ liệu giả.

    C4 sẽ tích hợp dữ liệu này với
    setHeatmapData() của heatmap.js.
    """

    daily_seconds = get_daily_focus_seconds(user)

    result = []

    for study_date in sorted(daily_seconds):

        seconds = daily_seconds[study_date]

        result.append({
            "date": study_date.isoformat(),
            "minutes": round(seconds / 60, 2)
        })

    return result
