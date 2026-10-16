
# ============================================================
# AI STUDYPLANNER
# planner/urls.py
#
# POMODORO WORKSPACE 2.0 - C4.1
#
# Nguyên tắc:
# - Giữ nguyên tất cả URL đang hoạt động
# - Không ảnh hưởng chức năng các Task khác
# - Tương thích với planner/views.py
# - Giữ API lưu phiên Pomodoro C2.3
# - Giữ Statistics API C3.2
# - Bổ sung Heatmap API C4.1
# - Chuẩn bị kết nối Heatmap Timeline V2.3
# ============================================================

from django.urls import path
from . import views


urlpatterns = [

    # ========================================================
    # 01. TASK MANAGEMENT
    # ========================================================

    # Trang danh sách nhiệm vụ.
    path(
        '',
        views.task_list,
        name='task_list'
    ),

    # Chuyển đổi trạng thái nhiệm vụ.
    path(
        'task/<int:task_id>/toggle/',
        views.toggle_task_status,
        name='toggle_task_status'
    ),

    # Xóa nhiệm vụ.
    path(
        'task/<int:task_id>/delete/',
        views.delete_task,
        name='delete_task'
    ),


    # ========================================================
    # 02. AUTHENTICATION
    # ========================================================

    # Đăng ký tài khoản.
    path(
        'register/',
        views.register_view,
        name='register'
    ),

    # Đăng nhập.
    path(
        'login/',
        views.login_view,
        name='login'
    ),

    # Đăng xuất.
    path(
        'logout/',
        views.logout_view,
        name='logout'
    ),


    # ========================================================
    # 03. CALENDAR
    # ========================================================

    # Trang lịch học.
    path(
        'calendar/',
        views.calendar_view,
        name='calendar_view'
    ),

    # API lấy sự kiện cho Calendar.
    path(
        'api/calendar-events/',
        views.calendar_events_api,
        name='calendar_events_api'
    ),

    # API cập nhật thời gian khi kéo thả lịch.
    path(
        'api/update-block-time/',
        views.update_block_time_api,
        name='update_block_time_api'
    ),


    # ========================================================
    # 04. RECURRING SCHEDULE
    # ========================================================

    # Danh sách lịch lặp lại.
    path(
        'recurring/',
        views.recurring_schedule_list,
        name='recurring_list'
    ),

    # Xóa lịch lặp lại.
    path(
        'recurring/<int:id>/delete/',
        views.delete_recurring,
        name='delete_recurring'
    ),


    # ========================================================
    # 05. AUTO SCHEDULING
    # ========================================================

    # Kích hoạt thuật toán lập lịch tự động.
    path(
        'auto-schedule/',
        views.trigger_auto_schedule,
        name='trigger_auto_schedule'
    ),


    # ========================================================
    # 06. POMODORO WORKSPACE 2.0
    # ========================================================

    # --------------------------------------------------------
    # A. POMODORO WORKSPACE
    #
    # URL:
    # GET /pomodoro/
    #
    # Giao diện:
    # - Pre-Focus
    # - In-Focus
    # - Post-Focus
    # - Celebration Sheet
    #
    # View:
    # planner/views.py -> pomodoro_view()
    # --------------------------------------------------------

    path(
        'pomodoro/',
        views.pomodoro_view,
        name='pomodoro_view'
    ),


    # --------------------------------------------------------
    # B. SAVE POMODORO SESSION API - C2.3
    #
    # URL:
    # POST /api/save-pomodoro/
    #
    # Frontend:
    # session-recorder.js
    #
    # View:
    # planner/views.py -> save_pomodoro_api()
    #
    # Service:
    # planner/pomodoro_services.py
    #
    # Hỗ trợ:
    # - completed
    # - deferred
    # - Scheduled Task
    # - Quick Goal
    # - session_uuid
    #
    # Yêu cầu:
    # - Người dùng đã đăng nhập
    # - CSRF token hợp lệ
    # - Dữ liệu JSON hợp lệ
    #
    # Database:
    # planner_pomodorolog
    # --------------------------------------------------------

    path(
        'api/save-pomodoro/',
        views.save_pomodoro_api,
        name='save_pomodoro_api'
    ),


    # --------------------------------------------------------
    # C. POMODORO STATISTICS API - C3.2
    #
    # URL:
    # GET /api/pomodoro-statistics/
    #
    # View:
    # planner/views.py -> pomodoro_statistics_api()
    #
    # Service:
    # planner/pomodoro_statistics.py
    #
    # Trả về:
    # - total_minutes
    # - total_seconds
    # - completed_sessions
    # - current_streak
    #
    # Chỉ tính phiên hoàn thành.
    # Chỉ đọc dữ liệu của user đang đăng nhập.
    # Không cập nhật database.
    #
    # Frontend:
    # statistics.js - C3.3
    # --------------------------------------------------------

    path(
        'api/pomodoro-statistics/',
        views.pomodoro_statistics_api,
        name='pomodoro_statistics_api'
    ),


    # --------------------------------------------------------
    # D. POMODORO HEATMAP API - C4.1
    #
    # URL:
    # GET /api/pomodoro-heatmap/
    #
    # View:
    # planner/views.py -> pomodoro_heatmap_api()
    #
    # Service:
    # planner/pomodoro_statistics.py
    # -> get_pomodoro_daily_data(user)
    #
    # Trả về:
    # - Ngày học theo định dạng YYYY-MM-DD
    # - Tổng số phút tập trung trong từng ngày
    #
    # Quy tắc:
    # - Chỉ tính phiên hoàn thành
    # - Không tính phiên Gác lại
    # - Sử dụng múi giờ Việt Nam
    # - Chỉ đọc dữ liệu user đang đăng nhập
    # - Không ghi dữ liệu vào database
    #
    # Frontend:
    # heatmap.js - Timeline V2.3
    #
    # C4.2 sẽ kết nối API với setHeatmapData().
    # --------------------------------------------------------

    path(
        'api/pomodoro-heatmap/',
        views.pomodoro_heatmap_api,
        name='pomodoro_heatmap_api'
    ),


    # ========================================================
    # 07. AI ASSISTANT
    # ========================================================

    # Trang trợ lý AI hỗ trợ lập kế hoạch học tập.
    path(
        'ai-assistant/',
        views.ai_assistant_view,
        name='ai_assistant_view'
    ),

]
