# planner/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from django.utils import timezone
from .forms import TaskForm, RecurringScheduleForm, RegisterForm
from .models import Task, ScheduleBlock, RecurringSchedule, PomodoroLog
from .scheduler import auto_generate_weekly_schedule
from .ai_assistant import analyze_schedule_with_ai
import json
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .models import UserProfile

@login_required
def task_list(request):
    if request.user.is_authenticated:
        tasks = Task.objects.filter(user=request.user).order_by('deadline')
    else:
        tasks = Task.objects.all().order_by('deadline')

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            new_task = form.save(commit=False)
            if request.user.is_authenticated:
                new_task.user = request.user
            else:
                # Gán tạm cho user đầu tiên trong DB để test nếu chưa login
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
    return render(request, 'planner/task_list.html', context)

def toggle_task_status(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if task.status == 'completed':
        task.status = 'todo'
    else:
        task.status = 'completed'
    task.save()
    return redirect('task_list')

def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return redirect('task_list')


def calendar_view(request):
    return render(request, 'planner/calendar.html')

@login_required
def calendar_events_api(request):
    user = request.user if request.user.is_authenticated else None

    events = []

    # A. Lấy các Task có deadline để hiển thị điểm mốc trên lịch
    task_filter = {'user': user} if user else {}
    tasks = Task.objects.filter(**task_filter)
    for task in tasks:
        events.append({
            'id': f"task-{task.id}",
            'title': f"Hạn nộp: {task.title}",
            'start': task.deadline.isoformat(),
            'allDay': False,
            'backgroundColor': '#ef4444' if task.priority == 1 else '#f59e0b',
            'borderColor': 'transparent',
            'extendedProps': {
                'type': 'task',
                'icon': 'fa-solid fa-clock',  # Chỉ định icon FontAwesome
                'subject': task.subject_name or 'Chung',
                'status': task.status
            }
        })

    # B. Lấy các ScheduleBlock (khối giờ học hoặc lịch bận)
    block_filter = {'user': user} if user else {}
    blocks = ScheduleBlock.objects.filter(**block_filter)
    for block in blocks:
        # Xác định icon tương ứng
        block_icon = 'fa-solid fa-lock' if block.is_fixed else 'fa-solid fa-book-open'
        events.append({
            'id': f"block-{block.id}",
            'title': block.title,
            'start': block.start_time.isoformat(),
            'end': block.end_time.isoformat(),
            'backgroundColor': '#64748b' if block.is_fixed else '#3b82f6',
            'borderColor': 'transparent',
            'extendedProps': {
                'type': 'block',
                'icon': block_icon,  # Chỉ định icon FontAwesome
                'is_fixed': block.is_fixed,
                'status': block.status
            }
        })

    return JsonResponse(events, safe=False)

@login_required
def recurring_schedule_list(request):
    user = request.user if request.user.is_authenticated else None
    if not user:
        from django.contrib.auth.models import User
        user = User.objects.first()

    schedules = RecurringSchedule.objects.filter(user=user).order_by('day_of_week', 'start_time')

    if request.method == 'POST':
        form = RecurringScheduleForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.user = user
            rec.save()
            return redirect('recurring_list')
    else:
        form = RecurringScheduleForm()

    return render(request, 'planner/recurring_list.html', {'schedules': schedules, 'form': form})


def delete_recurring(request, id):
    rec = get_object_or_404(RecurringSchedule, id=id)
    rec.delete()
    return redirect('recurring_list')


# View kích hoạt chạy thuật toán lập lịch tuần
def trigger_auto_schedule(request):
    user = request.user if request.user.is_authenticated else None
    if not user:
        from django.contrib.auth.models import User
        user = User.objects.first()

    count = auto_generate_weekly_schedule(user)
    return redirect('calendar_view')


# API cập nhật khi kéo thả (Drag and Drop) trên FullCalendar
@csrf_exempt
def update_block_time_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        event_id = data.get('id', '')

        # Chỉ cho phép chỉnh sửa ScheduleBlock, không cho dời hạn chót Task
        if event_id.startswith('block-'):
            block_id = int(event_id.replace('block-', ''))
            block = get_object_or_404(ScheduleBlock, id=block_id)
            block.start_time = datetime.fromisoformat(data.get('start'))
            block.end_time = datetime.fromisoformat(data.get('end'))
            block.status = 'confirmed'  # Người dùng đã chỉnh sửa/xác nhận
            block.save()
            return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'invalid request'}, status=400)

@login_required
def pomodoro_view(request):
    user = request.user if request.user.is_authenticated else None
    if not user:
        from django.contrib.auth.models import User
        user = User.objects.first()

    today = timezone.now().date()

    # Lấy các task đang cần làm để người dùng chọn bài học
    active_tasks = Task.objects.filter(user=user, status__in=['todo', 'in_progress']).order_by('priority', 'deadline')

    # Thống kê hôm nay
    today_logs = PomodoroLog.objects.filter(user=user, start_time__date=today, completed=True)
    today_minutes = today_logs.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
    today_sessions = today_logs.count()

    # Lịch sử 7 phiên gần nhất
    recent_logs = PomodoroLog.objects.filter(user=user).select_related('task').order_by('-start_time')[:7]

    context = {
        'active_tasks': active_tasks,
        'today_minutes': today_minutes,
        'today_sessions': today_sessions,
        'recent_logs': recent_logs,
    }
    return render(request, 'planner/pomodoro.html', context)


# 2. API nhận và lưu phiên học hoàn thành từ Javascript
@csrf_exempt
def save_pomodoro_api(request):
    if request.method == 'POST':
        user = request.user if request.user.is_authenticated else None
        if not user:
            from django.contrib.auth.models import User
            user = User.objects.first()

        data = json.loads(request.body)
        task_id = data.get('task_id')
        duration = data.get('duration_minutes', 25)
        completed = data.get('completed', True)

        task = Task.objects.filter(id=task_id, user=user).first() if task_id else None

        PomodoroLog.objects.create(
            user=user,
            task=task,
            duration_minutes=duration,
            completed=completed,
            start_time=timezone.now()
        )
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'invalid request'}, status=400)

@login_required
def ai_assistant_view(request):
    user = request.user if request.user.is_authenticated else None
    if not user:
        from django.contrib.auth.models import User
        user = User.objects.first()

    insights = analyze_schedule_with_ai(user)

    # Lấy thêm danh sách task ưu tiên cao để hiển thị kèm
    high_priority_tasks = Task.objects.filter(
        user=user,
        status__in=['todo', 'in_progress'],
        priority=1
    ).order_by('deadline')[:5]

    context = {
        'insights': insights,
        'high_priority_tasks': high_priority_tasks,
    }
    return render(request, 'planner/ai_assistant.html', context)
# 1. Đăng ký tài khoản
def register_view(request):
    if request.user.is_authenticated:
        return redirect('task_list')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Tự động tạo Profile gắn liền với User
            UserProfile.objects.get_or_create(user=user)
            login(request, user)  # Đăng ký xong tự động đăng nhập luôn
            return redirect('task_list')
    else:
        form = RegisterForm()
    return render(request, 'planner/register.html', {'form': form})

# 2. Đăng nhập
def login_view(request):
    if request.user.is_authenticated:
        return redirect('task_list')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('task_list')
    else:
        form = AuthenticationForm()
    return render(request, 'planner/login.html', {'form': form})

# 3. Đăng xuất
def logout_view(request):
    logout(request)
    return redirect('login')