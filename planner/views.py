
# ============================================================
# AI STUDYPLANNER
# planner/views.py
#
# POMODORO WORKSPACE 2.0 - C3.2
#
# Cập nhật:
# - Scheduled Task thật từ Django
# - Giữ API lưu phiên C2.3
# - Giữ CSRF cookie cho Pomodoro
# - Bổ sung Statistics API C3.2
#
# Không thay đổi logic các module khác.
# ============================================================

import json

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse

from django.views.decorators.csrf import (
    csrf_exempt,
    ensure_csrf_cookie,
)

from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from django.db.models import Sum
from django.utils import timezone

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required

from .forms import TaskForm, RecurringScheduleForm, RegisterForm

from .models import (
    Task,
    ScheduleBlock,
    RecurringSchedule,
    PomodoroLog,
    UserProfile,
)

from .scheduler import auto_generate_weekly_schedule
from .ai_assistant import analyze_schedule_with_ai

# C2.3 - Service lưu phiên Pomodoro.
from .pomodoro_services import (
    save_pomodoro_session,
    PomodoroValidationError,
)

# C3.2 - Service thống kê Pomodoro.
from .pomodoro_statistics import (
    get_pomodoro_statistics,
    get_pomodoro_daily_data,
)

# ============================================================
# 01. TASK MANAGEMENT
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

@login_required
def task_list(request):

    if request.user.is_authenticated:

        tasks = Task.objects.filter(
            user=request.user
        ).order_by('deadline')

    else:

        tasks = Task.objects.all().order_by('deadline')

    if request.method == 'POST':

        form = TaskForm(request.POST)

        if form.is_valid():

            new_task = form.save(commit=False)

            if request.user.is_authenticated:

                new_task.user = request.user

            else:

                # Gán tạm cho user đầu tiên trong DB
                # để test nếu chưa login.
                from django.contrib.auth.models import User

                new_task.user = User.objects.first()

            new_task.save()

            return redirect('task_list')

    else:

        form = TaskForm()

    context = {
        'tasks': tasks,
        'form': form,
    }

    return render(
        request,
        'planner/task_list.html',
        context
    )


def toggle_task_status(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id
    )

    if task.status == 'completed':

        task.status = 'todo'

    else:

        task.status = 'completed'

    task.save()

    return redirect('task_list')


def delete_task(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id
    )

    task.delete()

    return redirect('task_list')


# ============================================================
# 02. CALENDAR
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

def calendar_view(request):

    return render(
        request,
        'planner/calendar.html'
    )


@login_required
def calendar_events_api(request):

    user = (
        request.user
        if request.user.is_authenticated
        else None
    )

    events = []

    # --------------------------------------------------------
    # A. TASK DEADLINES
    # --------------------------------------------------------

    task_filter = (
        {'user': user}
        if user
        else {}
    )

    tasks = Task.objects.filter(
        **task_filter
    )

    for task in tasks:

        events.append({
            'id': f"task-{task.id}",

            'title': f"Hạn nộp: {task.title}",

            'start': task.deadline.isoformat(),

            'allDay': False,

            'backgroundColor': (
                '#ef4444'
                if task.priority == 1
                else '#f59e0b'
            ),

            'borderColor': 'transparent',

            'extendedProps': {
                'type': 'task',
                'icon': 'fa-solid fa-clock',
                'subject': task.subject_name or 'Chung',
                'status': task.status,
            }
        })

    # --------------------------------------------------------
    # B. SCHEDULE BLOCKS
    # --------------------------------------------------------

    block_filter = (
        {'user': user}
        if user
        else {}
    )

    blocks = ScheduleBlock.objects.filter(
        **block_filter
    )

    for block in blocks:

        block_icon = (
            'fa-solid fa-lock'
            if block.is_fixed
            else 'fa-solid fa-book-open'
        )

        events.append({
            'id': f"block-{block.id}",

            'title': block.title,

            'start': block.start_time.isoformat(),

            'end': block.end_time.isoformat(),

            'backgroundColor': (
                '#64748b'
                if block.is_fixed
                else '#3b82f6'
            ),

            'borderColor': 'transparent',

            'extendedProps': {
                'type': 'block',
                'icon': block_icon,
                'is_fixed': block.is_fixed,
                'status': block.status,
            }
        })

    return JsonResponse(
        events,
        safe=False
    )


# ============================================================
# 03. RECURRING SCHEDULE
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

@login_required
def recurring_schedule_list(request):

    user = (
        request.user
        if request.user.is_authenticated
        else None
    )

    if not user:

        from django.contrib.auth.models import User

        user = User.objects.first()

    schedules = RecurringSchedule.objects.filter(
        user=user
    ).order_by(
        'day_of_week',
        'start_time'
    )

    if request.method == 'POST':

        form = RecurringScheduleForm(request.POST)

        if form.is_valid():

            rec = form.save(commit=False)

            rec.user = user

            rec.save()

            return redirect('recurring_list')

    else:

        form = RecurringScheduleForm()

    return render(
        request,
        'planner/recurring_list.html',
        {
            'schedules': schedules,
            'form': form
        }
    )


def delete_recurring(request, id):

    rec = get_object_or_404(
        RecurringSchedule,
        id=id
    )

    rec.delete()

    return redirect(
        'recurring_list'
    )


# ============================================================
# 04. AUTO SCHEDULE
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

def trigger_auto_schedule(request):

    user = (
        request.user
        if request.user.is_authenticated
        else None
    )

    if not user:

        from django.contrib.auth.models import User

        user = User.objects.first()

    count = auto_generate_weekly_schedule(
        user
    )

    return redirect(
        'calendar_view'
    )


# ============================================================
# 05. CALENDAR DRAG & DROP API
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

@csrf_exempt
def update_block_time_api(request):

    if request.method == 'POST':

        data = json.loads(
            request.body
        )

        event_id = data.get(
            'id',
            ''
        )

        # Chỉ chỉnh ScheduleBlock.
        if event_id.startswith('block-'):

            block_id = int(
                event_id.replace(
                    'block-',
                    ''
                )
            )

            block = get_object_or_404(
                ScheduleBlock,
                id=block_id
            )

            # Giữ nguyên xử lý Calendar hiện tại.
            block.start_time = datetime.fromisoformat(
                data.get('start')
            )

            block.end_time = datetime.fromisoformat(
                data.get('end')
            )

            block.status = 'confirmed'

            block.save()

            return JsonResponse({
                'status': 'success'
            })

    return JsonResponse(
        {
            'status': 'invalid request'
        },
        status=400
    )


# ============================================================
# 06. POMODORO VIEW - C2.3.2
#
# Giữ:
# - Task thật
# - Context cũ
# - CSRF cookie
#
# Statistics Dashboard sẽ tích hợp ở C3.3.
# ============================================================

@login_required
@ensure_csrf_cookie
def pomodoro_view(request):

    user = request.user

    today = timezone.now().date()

    # --------------------------------------------------------
    # A. TASK THẬT CỦA NGƯỜI DÙNG
    # --------------------------------------------------------

    active_tasks = Task.objects.filter(
        user=user,
        status__in=[
            'todo',
            'in_progress'
        ]
    ).order_by(
        'priority',
        'deadline'
    )

    # --------------------------------------------------------
    # B. DỮ LIỆU CHO TASK SELECTOR V13
    # --------------------------------------------------------

    pomodoro_tasks = [
        {
            'id': task.id,
            'taskId': task.id,
            'name': task.title,
            'type': 'scheduled',
        }
        for task in active_tasks
    ]

    # --------------------------------------------------------
    # C. THỐNG KÊ HÔM NAY - LOGIC CŨ
    #
    # Giữ nguyên để không gây thay đổi
    # các phần đang phụ thuộc vào context.
    # --------------------------------------------------------

    today_logs = PomodoroLog.objects.filter(
        user=user,
        start_time__date=today,
        completed=True
    )

    today_minutes = (
        today_logs.aggregate(
            Sum('duration_minutes')
        )['duration_minutes__sum']
        or 0
    )

    today_sessions = today_logs.count()

    # --------------------------------------------------------
    # D. LỊCH SỬ 7 PHIÊN GẦN NHẤT
    # --------------------------------------------------------

    recent_logs = (
        PomodoroLog.objects
        .filter(user=user)
        .select_related('task')
        .order_by('-start_time')[:7]
    )

    # --------------------------------------------------------
    # E. TEMPLATE CONTEXT
    # --------------------------------------------------------

    context = {
        'active_tasks': active_tasks,
        'today_minutes': today_minutes,
        'today_sessions': today_sessions,
        'recent_logs': recent_logs,

        # C2.3.2 - Task thật từ Django.
        'pomodoro_tasks': pomodoro_tasks,
    }

    return render(
        request,
        'planner/pomodoro/index.html',
        context
    )


# ============================================================
# 07. SAVE POMODORO API - C2.3
#
# POST /api/save-pomodoro/
#
# Giữ nguyên cơ chế lưu đã kiểm thử:
# - Scheduled Task
# - Quick Goal
# - Completed / Deferred
# - session_uuid
# - Chống ghi trùng
# ============================================================

@login_required
@require_POST
def save_pomodoro_api(request):

    # --------------------------------------------------------
    # A. KIỂM TRA CONTENT TYPE
    # --------------------------------------------------------

    if request.content_type != "application/json":

        return JsonResponse(
            {
                'status': 'error',
                'message': 'Yêu cầu phải gửi dữ liệu JSON.'
            },
            status=415
        )

    # --------------------------------------------------------
    # B. ĐỌC JSON
    # --------------------------------------------------------

    try:

        data = json.loads(
            request.body.decode('utf-8')
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError
    ):

        return JsonResponse(
            {
                'status': 'error',
                'message': 'Dữ liệu JSON không hợp lệ.'
            },
            status=400
        )

    # --------------------------------------------------------
    # C. VALIDATE VÀ LƯU PHIÊN
    # --------------------------------------------------------

    try:

        log = save_pomodoro_session(
            user=request.user,
            data=data
        )

    except PomodoroValidationError as error:

        return JsonResponse(
            {
                'status': 'error',
                'message': str(error)
            },
            status=400
        )

    # --------------------------------------------------------
    # D. TRẢ JSON
    # --------------------------------------------------------

    return JsonResponse(
        {
            'status': 'success',

            'message': 'Đã lưu phiên tập trung.',

            'data': {
                'id': log.id,

                'task_id': log.task_id,

                'status': log.status,

                'completed': log.completed,

                'duration_minutes': (
                    log.duration_minutes
                ),

                'actual_seconds': (
                    log.actual_seconds
                ),

                'remaining_seconds': (
                    log.remaining_seconds
                ),

                'start_time': (
                    log.start_time.isoformat()
                ),

                'ended_at': (
                    log.ended_at.isoformat()
                    if log.ended_at
                    else None
                ),

                'resumed_from_id': (
                    log.resumed_from_id
                ),
            }
        },
        status=201
    )


# ============================================================
# 08. POMODORO STATISTICS API - C3.2
#
# GET /api/pomodoro-statistics/
#
# Chức năng:
# - Lấy dữ liệu thống kê thật từ PomodoroLog.
# - Chỉ truy vấn dữ liệu user đang đăng nhập.
# - Chỉ chấp nhận HTTP GET.
# - Không thay đổi database.
#
# Statistics Service đã được kiểm thử ở C3.1.
# ============================================================

@login_required
@require_GET
def pomodoro_statistics_api(request):

    # --------------------------------------------------------
    # A. NGƯỜI DÙNG HIỆN TẠI
    # --------------------------------------------------------

    user = request.user

    # --------------------------------------------------------
    # B. TÍNH THỐNG KÊ
    #
    # Service chịu trách nhiệm:
    # - Lọc các phiên completed.
    # - Tương thích bản ghi lịch sử.
    # - Tính tổng thời gian thực tế.
    # - Tính streak theo giờ Việt Nam.
    # --------------------------------------------------------

    statistics = get_pomodoro_statistics(
        user
    )

    # --------------------------------------------------------
    # C. TRẢ JSON
    #
    # HTTP 200:
    # {
    #     "status": "success",
    #     "data": {
    #         "total_minutes": 4,
    #         "total_seconds": 240,
    #         "completed_sessions": 4,
    #         "current_streak": 1
    #     }
    # }
    # --------------------------------------------------------

    return JsonResponse(
        {
            'status': 'success',
            'data': statistics
        },
        status=200
    )


# ============================================================
# 09. POMODORO HEATMAP API - C4.1
#
# GET /api/pomodoro-heatmap/
#
# Chức năng:
# - Trả tổng số phút tập trung theo ngày.
# - Chỉ lấy phiên đã hoàn thành.
# - Không cộng phiên Gác lại.
# - Sử dụng múi giờ Việt Nam từ Statistics Service.
# - Chỉ lấy dữ liệu của người dùng đăng nhập.
# - Không ghi hoặc cập nhật database.
#
# Frontend:
# heatmap.js V2.3 -> setHeatmapData()
# ============================================================

@login_required
@require_GET
def pomodoro_heatmap_api(request):

    # Người dùng hiện tại.
    user = request.user

    # Lấy dữ liệu thực tế từ PomodoroLog.
    daily_data = get_pomodoro_daily_data(user)

    # Trả kết quả cho Frontend.
    return JsonResponse(
        {
            'status': 'success',
            'data': {
                'days': daily_data
            }
        },
        status=200
    )

# ============================================================
# 10. AI ASSISTANT
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

@login_required
def ai_assistant_view(request):

    user = (
        request.user
        if request.user.is_authenticated
        else None
    )

    if not user:

        from django.contrib.auth.models import User

        user = User.objects.first()

    insights = analyze_schedule_with_ai(
        user
    )

    high_priority_tasks = Task.objects.filter(
        user=user,
        status__in=[
            'todo',
            'in_progress'
        ],
        priority=1
    ).order_by(
        'deadline'
    )[:5]

    context = {
        'insights': insights,
        'high_priority_tasks': high_priority_tasks,
    }

    return render(
        request,
        'planner/ai_assistant.html',
        context
    )


# ============================================================
# 11. REGISTER
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

def register_view(request):

    if request.user.is_authenticated:

        return redirect(
            'task_list'
        )

    if request.method == 'POST':

        form = RegisterForm(
            request.POST
        )

        if form.is_valid():

            user = form.save()

            UserProfile.objects.get_or_create(
                user=user
            )

            login(
                request,
                user
            )

            return redirect(
                'task_list'
            )

    else:

        form = RegisterForm()

    return render(
        request,
        'planner/register.html',
        {
            'form': form
        }
    )


# ============================================================
# 12. LOGIN
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

def login_view(request):

    if request.user.is_authenticated:

        return redirect(
            'task_list'
        )

    if request.method == 'POST':

        form = AuthenticationForm(
            request,
            data=request.POST
        )

        if form.is_valid():

            user = form.get_user()

            login(
                request,
                user
            )

            return redirect(
                'task_list'
            )

    else:

        form = AuthenticationForm()

    return render(
        request,
        'planner/login.html',
        {
            'form': form
        }
    )


# ============================================================
# 13. LOGOUT
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

def logout_view(request):

    logout(
        request
    )

    return redirect(
        'login'
    )
