from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from planner.models import Course, ScheduleBlock, Task


class Command(BaseCommand):
    help = 'Create sample courses, tasks, and calendar events for an existing user.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            help='Username that will own the sample data. Defaults to the first user.'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        username = options['username']
        users = user_model.objects.order_by('pk')
        user = users.filter(username=username).first() if username else users.first()

        if user is None:
            raise CommandError(
                'No user exists. Register an account first or create one with createsuperuser.'
            )

        courses = {}
        for code, name in (
            ('PY101', 'Lập trình Python'),
            ('DB201', 'Cơ sở dữ liệu'),
            ('MA101', 'Toán rời rạc'),
        ):
            course, _ = Course.objects.get_or_create(
                user=user,
                code=code,
                defaults={'name': name}
            )
            courses[code] = course

        now = timezone.localtime()
        tasks = (
            (
                'Hoàn thành bài tập Python',
                'PY101',
                2,
                90,
                1,
            ),
            (
                'Thiết kế sơ đồ cơ sở dữ liệu',
                'DB201',
                4,
                120,
                2,
            ),
            (
                'Ôn tập quan hệ và đồ thị',
                'MA101',
                5,
                60,
                3,
            ),
        )
        task_by_title = {}
        for title, course_code, days_until_deadline, minutes, priority in tasks:
            task, _ = Task.objects.get_or_create(
                user=user,
                title=title,
                defaults={
                    'course': courses[course_code],
                    'subject_name': courses[course_code].name,
                    'deadline': now + timedelta(days=days_until_deadline),
                    'estimated_minutes': minutes,
                    'priority': priority,
                }
            )
            task_by_title[title] = task

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
            event_date = now.date() + timedelta(days=days_ahead)
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
