
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
import os
import uuid
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse, JsonResponse

from django.views.decorators.csrf import (
    ensure_csrf_cookie,
)

from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime

from .forms import (
    CourseForm,
    IcsImportForm,
    StudyHoursForm,
    TaskForm,
    ScheduleBlockForm,
    RecurringScheduleForm,
    RegisterForm,
)

from .models import (
    Course,
    Task,
    ScheduleBlock,
    RecurringSchedule,
    PomodoroLog,
    UserProfile,
)

from .scheduler import generate_weekly_plan
from .ai_assistant import analyze_schedule_with_ai
from .icalendar import build_user_calendar, import_ics_for_user
from .risk import assess_task, assess_user_tasks

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
    tasks = Task.objects.filter(
        user=request.user
    ).select_related('course').order_by('deadline')

    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, f'Đã thêm nhiệm vụ "{task.title}".')
            return redirect('task_list')
    else:
        form = TaskForm(user=request.user)

    now = timezone.now()
    task_rows = [
        {'task': task, 'risk': assess_task(task, now)}
        for task in tasks
    ]
    open_rows = [row for row in task_rows if row['task'].status != 'completed']
    week_logs = PomodoroLog.objects.filter(
        user=request.user,
        start_time__gte=now - timedelta(days=7),
        completed=True,
    ).exclude(status='deferred')
    stats = {
        'open': len(open_rows),
        'completed': len(task_rows) - len(open_rows),
        'high_risk': sum(1 for row in open_rows if row['risk'].level == 'high'),
        'focus_minutes': sum(
            (log.actual_seconds or log.duration_minutes * 60) for log in week_logs
        ) // 60,
    }
    status_filter = request.GET.get('status', 'open')
    if status_filter == 'open':
        visible_rows = open_rows
    elif status_filter == 'completed':
        visible_rows = [row for row in task_rows if row['task'].status == 'completed']
    else:
        status_filter = 'all'
        visible_rows = task_rows

    context = {
        'tasks': tasks,
        'task_rows': visible_rows,
        'status_filter': status_filter,
        'stats': stats,
        'form': form,
        'today_blocks': ScheduleBlock.objects.filter(
            user=request.user,
            start_time__date=timezone.localdate(),
        ).order_by('start_time')[:6],
    }

    return render(
        request,
        'planner/task_list.html',
        context
    )


@login_required
@require_POST
def toggle_task_status(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user,
    )

    if task.status == 'completed':

        task.status = 'todo'

    else:

        task.status = 'completed'

    task.save()

    return redirect('task_list')


@login_required
@require_POST
def delete_task(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user,
    )

    material_name = task.material_file.name if task.material_file else None
    task.delete()
    if material_name:
        default_storage.delete(material_name)

    return redirect('task_list')


@login_required
@require_http_methods(['GET', 'POST'])
def edit_task(request, task_id):
    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user,
    )

    if request.method == 'POST':
        old_material_name = (
            task.material_file.name
            if task.material_file
            else None
        )
        form = TaskForm(
            request.POST,
            request.FILES,
            instance=task,
            user=request.user,
        )
        if form.is_valid():
            task = form.save()
            if (
                old_material_name
                and task.material_file.name != old_material_name
            ):
                default_storage.delete(old_material_name)
            return redirect('task_list')
    else:
        form = TaskForm(instance=task, user=request.user)

    return render(
        request,
        'planner/task_form.html',
        {'form': form, 'task': task},
    )


@login_required
@require_GET
def download_study_material(request, task_id):
    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user,
    )
    if not task.material_file:
        raise Http404('Nhiệm vụ không có tài liệu đính kèm.')

    response = FileResponse(
        task.material_file.open('rb'),
        as_attachment=True,
        filename=os.path.basename(task.material_file.name),
    )
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


# ============================================================
# 02. CALENDAR
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

@login_required
def calendar_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    feed_url = request.build_absolute_uri(
        reverse('calendar_feed', args=[profile.calendar_token])
    )
    return render(
        request,
        'planner/calendar.html',
        {
            'feed_url': feed_url,
            'webcal_url': feed_url.replace('https://', 'webcal://').replace('http://', 'webcal://'),
            'import_form': IcsImportForm(),
        },
    )


@require_GET
def calendar_feed(request, token):
    """Link đăng ký lịch (subscribe) không cần đăng nhập, bảo vệ bằng token bí mật."""
    profile = get_object_or_404(UserProfile, calendar_token=token)
    response = HttpResponse(
        build_user_calendar(profile.user),
        content_type='text/calendar; charset=utf-8',
    )
    response['Content-Disposition'] = 'inline; filename="ai-study-planner.ics"'
    response['Cache-Control'] = 'private, max-age=300'
    return response


@login_required
@require_POST
def import_calendar_ics(request):
    form = IcsImportForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, form.errors.get('ics_file', ['Tệp không hợp lệ.'])[0])
        return redirect('calendar_view')
    raw = form.cleaned_data['ics_file'].read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    created = import_ics_for_user(request.user, text)
    messages.success(request, f'Đã nhập {created} sự kiện từ tệp .ics vào lịch bận.')
    return redirect('calendar_view')


@login_required
@require_POST
def reset_calendar_token(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.calendar_token = uuid.uuid4()
    profile.save(update_fields=['calendar_token'])
    messages.success(request, 'Đã tạo link đăng ký lịch mới; link cũ không còn hoạt động.')
    return redirect('calendar_view')


@login_required
@require_GET
def export_calendar_ics(request):
    response = HttpResponse(
        build_user_calendar(request.user),
        content_type='text/calendar; charset=utf-8',
    )
    response['Content-Disposition'] = 'attachment; filename="ai-study-planner.ics"'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def calendar_events_api(request):

    user = request.user

    events = []

    # --------------------------------------------------------
    # A. TASK DEADLINES
    # --------------------------------------------------------

    tasks = Task.objects.filter(user=user)

    for task in tasks:

        events.append({
            'id': f"task-{task.id}",

            'title': f"Hạn nộp: {task.title}",

            'start': task.deadline.isoformat(),

            'allDay': False,

            'backgroundColor': (
                '#10b981'
                if task.status == 'completed'
                else ('#ef4444' if task.priority == 1 else '#f59e0b')
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

    blocks = ScheduleBlock.objects.filter(user=user)

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
                else ('#8b5cf6' if block.status == 'suggested' else '#4f46e5')
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


@login_required
@require_http_methods(['GET', 'POST'])
def create_schedule_block(request):
    if request.method == 'POST':
        form = ScheduleBlockForm(request.POST, user=request.user)
        if form.is_valid():
            block = form.save(commit=False)
            block.user = request.user
            block.is_fixed = False
            block.status = 'confirmed'
            block.save()
            return redirect('calendar_view')
    else:
        form = ScheduleBlockForm(user=request.user)

    return render(
        request,
        'planner/schedule_block_form.html',
        {'form': form, 'is_create': True},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def edit_schedule_block(request, block_id):
    block = get_object_or_404(
        ScheduleBlock,
        id=block_id,
        user=request.user,
        is_fixed=False,
    )

    if request.method == 'POST':
        form = ScheduleBlockForm(
            request.POST,
            instance=block,
            user=request.user,
        )
        if form.is_valid():
            updated_block = form.save(commit=False)
            updated_block.status = 'confirmed'
            updated_block.save()
            return redirect('calendar_view')
    else:
        form = ScheduleBlockForm(instance=block, user=request.user)

    return render(
        request,
        'planner/schedule_block_form.html',
        {'form': form, 'is_create': False, 'schedule_event': block},
    )


@login_required
@require_POST
def delete_schedule_block(request, block_id):
    block = get_object_or_404(
        ScheduleBlock,
        id=block_id,
        user=request.user,
        is_fixed=False,
    )
    block.delete()
    return redirect('calendar_view')


# ============================================================
# 03. RECURRING SCHEDULE
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

@login_required
def recurring_schedule_list(request):
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    schedules = RecurringSchedule.objects.filter(
        user=user
    ).order_by(
        'day_of_week',
        'start_time'
    )

    form = RecurringScheduleForm()
    hours_form = StudyHoursForm(instance=profile)

    if request.method == 'POST':
        if request.POST.get('form') == 'hours':
            hours_form = StudyHoursForm(request.POST, instance=profile)
            if hours_form.is_valid():
                hours_form.save()
                messages.success(request, 'Đã lưu khung giờ ngủ / học.')
                return redirect('recurring_list')
        else:
            form = RecurringScheduleForm(request.POST)
            if form.is_valid():
                rec = form.save(commit=False)
                rec.user = user
                rec.save()
                messages.success(request, f'Đã thêm lịch bận "{rec.title}".')
                return redirect('recurring_list')

    return render(
        request,
        'planner/recurring_list.html',
        {
            'schedules': schedules,
            'form': form,
            'hours_form': hours_form,
        }
    )


@login_required
@require_POST
def delete_recurring(request, id):
    rec = get_object_or_404(
        RecurringSchedule,
        id=id,
        user=request.user,
    )
    rec.delete()
    return redirect(
        'recurring_list'
    )


# ============================================================
# 04. AUTO SCHEDULE
# ============================================================

@login_required
@require_POST
def trigger_auto_schedule(request):
    result = generate_weekly_plan(request.user)
    if result['created']:
        messages.success(
            request,
            f"Đã sinh {result['created']} phiên học gợi ý cho 7 ngày tới. "
            'Kéo thả để chỉnh sửa; phiên đã chỉnh sẽ được giữ lại.'
        )
    else:
        messages.info(request, 'Không có nhiệm vụ nào cần xếp lịch.')
    for title, minutes in result['unscheduled'].items():
        messages.warning(
            request,
            f'"{title}" còn {minutes} phút chưa xếp được trước deadline — '
            'hãy giảm lịch bận hoặc dời deadline.'
        )
    return redirect(
        'calendar_view'
    )


# ============================================================
# 04b. COURSES
# ============================================================

@login_required
@require_http_methods(['GET', 'POST'])
def course_list(request):
    form = CourseForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        course = form.save(commit=False)
        course.user = request.user
        course.save()
        messages.success(request, f'Đã thêm môn {course.code}.')
        return redirect('course_list')
    courses = (
        Course.objects.filter(user=request.user)
        .annotate(task_count=Count('tasks'))
    )
    return render(request, 'planner/course_list.html', {'courses': courses, 'form': form})


@login_required
@require_POST
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, user=request.user)
    course.delete()
    messages.success(request, f'Đã xóa môn {course.code}.')
    return redirect('course_list')


# ============================================================
# 04c. RISK API
# ============================================================

@login_required
@require_GET
def risk_api(request):
    data = [
        {
            'task_id': task.id,
            'title': task.title,
            'deadline': task.deadline.isoformat(),
            'score': risk.score,
            'level': risk.level,
            'remaining_minutes': risk.remaining_minutes,
            'reasons': risk.reasons,
        }
        for task, risk in assess_user_tasks(request.user)
    ]
    return JsonResponse({'tasks': data})


# ============================================================
# 05. CALENDAR DRAG & DROP API
# GIỮ NGUYÊN LOGIC CŨ
# ============================================================

@login_required
@require_POST
def update_block_time_api(request):
    try:
        data = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {'status': 'error', 'message': 'Dữ liệu JSON không hợp lệ.'},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {'status': 'error', 'message': 'Nội dung JSON phải là một đối tượng.'},
            status=400,
        )

    event_id = data.get('id', '')
    if not isinstance(event_id, str) or not event_id.startswith('block-'):
        return JsonResponse(
            {'status': 'error', 'message': 'Sự kiện không hợp lệ.'},
            status=400,
        )

    try:
        block_id = int(event_id.removeprefix('block-'))
    except ValueError:
        return JsonResponse(
            {'status': 'error', 'message': 'Mã sự kiện không hợp lệ.'},
            status=400,
        )

    block = get_object_or_404(
        ScheduleBlock,
        id=block_id,
        user=request.user,
        is_fixed=False,
    )
    start_value = data.get('start', '')
    end_value = data.get('end', '')
    if not isinstance(start_value, str) or not isinstance(end_value, str):
        return JsonResponse(
            {'status': 'error', 'message': 'Thời gian sự kiện không hợp lệ.'},
            status=400,
        )

    start_time = parse_datetime(start_value)
    end_time = parse_datetime(end_value)
    if not start_time or not end_time:
        return JsonResponse(
            {'status': 'error', 'message': 'Khoảng thời gian không hợp lệ.'},
            status=400,
        )

    if timezone.is_naive(start_time):
        start_time = timezone.make_aware(start_time)
    if timezone.is_naive(end_time):
        end_time = timezone.make_aware(end_time)

    if end_time <= start_time:
        return JsonResponse(
            {'status': 'error', 'message': 'Khoảng thời gian không hợp lệ.'},
            status=400,
        )

    block.start_time = start_time
    block.end_time = end_time
    block.status = 'confirmed'
    block.save(update_fields=['start_time', 'end_time', 'status'])

    return JsonResponse({'status': 'success'})


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
    insights = analyze_schedule_with_ai(request.user)
    risks = assess_user_tasks(request.user)
    context = {
        'insights': insights,
        'risk_rows': risks[:8],
        'high_count': sum(1 for _, r in risks if r.level == 'high'),
        'medium_count': sum(1 for _, r in risks if r.level == 'medium'),
        'low_count': sum(1 for _, r in risks if r.level == 'low'),
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
