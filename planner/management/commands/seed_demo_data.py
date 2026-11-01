from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from planner.models import Course, RecurringSchedule, ScheduleBlock, Task, UserProfile


COURSES = (
    ('PY101', 'Lập trình Python'),
    ('DB201', 'Cơ sở dữ liệu'),
    ('MA101', 'Toán rời rạc'),
    ('EN102', 'Tiếng Anh chuyên ngành'),
)

# 8 task mẫu cho demo thuật toán sinh kế hoạch tuần (Task 3):
# (tiêu đề, mã môn, số giờ tới hạn, phút ước tính, ưu tiên)
SAMPLE_TASKS = (
    ('Hoàn thành bài tập Python', 'PY101', 48, 90, 1),
    ('Thiết kế sơ đồ cơ sở dữ liệu', 'DB201', 96, 120, 2),
    ('Ôn tập quan hệ và đồ thị', 'MA101', 120, 60, 3),
    ('Nộp báo cáo đồ án giữa kỳ', 'PY101', 20, 180, 1),
    ('Viết truy vấn SQL nâng cao', 'DB201', 72, 75, 2),
    ('Làm đề luyện tập Toán rời rạc', 'MA101', 144, 90, 2),
    ('Học 50 từ vựng chuyên ngành', 'EN102', 60, 45, 3),
    ('Chuẩn bị slide thuyết trình nhóm', 'EN102', 160, 100, 1),
)

# Lịch bận lặp lại hàng tuần: (tiêu đề, thứ, bắt đầu, kết thúc, loại)
RECURRING = (
    ('Học trên lớp', 0, time(7, 30), time(11, 30), 'school'),
    ('Học trên lớp', 2, time(13, 0), time(17, 0), 'school'),
    ('Học trên lớp', 4, time(7, 30), time(11, 30), 'school'),
    ('Ca làm thêm', 1, time(18, 0), time(21, 0), 'part_time'),
    ('Ca làm thêm', 5, time(8, 0), time(12, 0), 'part_time'),
)


class Command(BaseCommand):
    help = 'Create sample courses, 8 tasks, weekly busy schedule and calendar events for a user.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            help='Username that will own the sample data. Defaults to the first user.'
        )
        parser.add_argument(
            '--create-user',
            action='store_true',
            help='Create the user (password = --password) if it does not exist.',
        )
        parser.add_argument(
            '--password',
            default='demo12345',
            help='Password used together with --create-user (default: demo12345).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        username = options['username']
        users = user_model.objects.order_by('pk')
        user = users.filter(username=username).first() if username else users.first()

        if user is None and options['create_user']:
            user = user_model.objects.create_user(
                username=username or 'demo',
                email=f"{username or 'demo'}@example.com",
                password=options['password'],
            )
            self.stdout.write(f'Created user "{user.username}".')

        if user is None:
            raise CommandError(
                'No user exists. Register an account first or create one with createsuperuser.'
            )

        UserProfile.objects.get_or_create(user=user)

        courses = {}
        for code, name in COURSES:
            course, _ = Course.objects.get_or_create(
                user=user,
                code=code,
                defaults={'name': name}
            )
            courses[code] = course

        now = timezone.now()
        task_by_title = {}
        for title, course_code, hours_until_deadline, minutes, priority in SAMPLE_TASKS:
            task, _ = Task.objects.get_or_create(
                user=user,
                title=title,
                defaults={
                    'course': courses[course_code],
                    'subject_name': courses[course_code].name,
                    'deadline': now + timedelta(hours=hours_until_deadline),
                    'estimated_minutes': minutes,
                    'priority': priority,
                }
            )
            task_by_title[title] = task

        for title, day, start, end, category in RECURRING:
            RecurringSchedule.objects.get_or_create(
                user=user,
                title=title,
                day_of_week=day,
                start_time=start,
                defaults={'end_time': end, 'category': category},
            )

        local_today = timezone.localdate()
        events = (
            (
                'Ôn tập Python',
                task_by_title['Hoàn thành bài tập Python'],
                1,
                time(19, 0),
                time(20, 0),
            ),
            (
                'Làm bài Cơ sở dữ liệu',
                task_by_title['Thiết kế sơ đồ cơ sở dữ liệu'],
                2,
                time(19, 30),
                time(20, 30),
            ),
        )
        for title, task, days_ahead, start_time, end_time in events:
            event_date = local_today + timedelta(days=days_ahead)
            start = timezone.make_aware(
                datetime.combine(event_date, start_time)
            )
            end = timezone.make_aware(
                datetime.combine(event_date, end_time)
            )
            ScheduleBlock.objects.get_or_create(
                user=user,
                title=title,
                start_time=start,
                defaults={
                    'task': task,
                    'end_time': end,
                    'is_fixed': True,
                    'status': 'confirmed',
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Sample data is ready for user "{user.get_username()}".'
            )
        )
