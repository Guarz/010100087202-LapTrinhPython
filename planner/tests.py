import io
import json
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .forms import ScheduleBlockForm, TaskForm
from .models import Course, ScheduleBlock, Task, UserProfile


class CourseTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            password='test-password'
        )
        self.course = Course.objects.create(
            user=self.user,
            code='PY101',
            name='Lập trình Python'
        )

    def test_task_form_only_lists_courses_owned_by_user(self):
        other_user = User.objects.create_user(
            username='other',
            password='test-password'
        )
        other_course = Course.objects.create(
            user=other_user,
            code='PY101',
            name='Khóa học riêng'
        )

        form = TaskForm(user=self.user)

        self.assertEqual(
            list(form.fields['course'].queryset),
            [self.course]
        )
        self.assertNotIn(
            other_course,
            form.fields['course'].queryset
        )

    def test_task_form_copies_course_name_to_legacy_subject_field(self):
        deadline = timezone.localtime() + timedelta(days=1)
        form = TaskForm(
            data={
                'title': 'Bài tập tuần 1',
                'course': str(self.course.pk),
                'subject_name': '',
                'deadline': deadline.strftime('%Y-%m-%dT%H:%M'),
                'estimated_minutes': '60',
                'priority': '2',
                'material_url': '',
            },
            user=self.user
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data['subject_name'],
            self.course.name
        )


class StudyMaterialUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='material-owner',
            email='owner@example.com',
            password='test-password',
        )
        self.other_user = User.objects.create_user(
            username='other-material-owner',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_owner_can_upload_and_download_material_but_other_users_cannot(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            deadline = timezone.localtime() + timedelta(days=1)
            response = self.client.post(
                '/',
                {
                    'title': 'Bài có tài liệu',
                    'subject_name': 'Python',
                    'deadline': deadline.strftime('%Y-%m-%dT%H:%M'),
                    'estimated_minutes': '60',
                    'priority': '2',
                    'material_url': '',
                    'material_file': SimpleUploadedFile(
                        'notes.pdf',
                        b'%PDF-1.4 study notes',
                        content_type='application/pdf',
                    ),
                },
            )
            self.assertRedirects(response, '/')
            task = Task.objects.get(title='Bài có tài liệu')
            self.assertTrue(task.material_file.name.startswith(
                f'study_materials/user_{self.user.pk}/'
            ))

            response = self.client.get(
                f'/task/{task.pk}/material/'
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment;', response['Content-Disposition'])
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 study notes')

            self.client.force_login(self.other_user)
            self.assertEqual(
                self.client.get(f'/task/{task.pk}/material/').status_code,
                404,
            )

    def test_upload_rejects_unsupported_extensions(self):
        deadline = timezone.localtime() + timedelta(days=1)
        response = self.client.post(
            '/',
            {
                'title': 'File không hợp lệ',
                'subject_name': 'Python',
                'deadline': deadline.strftime('%Y-%m-%dT%H:%M'),
                'estimated_minutes': '60',
                'priority': '2',
                'material_file': SimpleUploadedFile('payload.exe', b'not allowed'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.filter(title='File không hợp lệ').exists())

    def test_upload_rejects_files_over_10_megabytes(self):
        deadline = timezone.localtime() + timedelta(days=1)
        response = self.client.post(
            '/',
            {
                'title': 'File quá lớn',
                'subject_name': 'Python',
                'deadline': deadline.strftime('%Y-%m-%dT%H:%M'),
                'estimated_minutes': '60',
                'priority': '2',
                'material_file': SimpleUploadedFile(
                    'large.txt',
                    b'x' * (10 * 1024 * 1024 + 1),
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.filter(title='File quá lớn').exists())

    def test_download_requires_login_and_existing_attachment(self):
        task = Task.objects.create(
            user=self.user,
            title='Không có tài liệu',
            deadline=timezone.now() + timedelta(days=1),
            estimated_minutes=30,
        )
        self.client.logout()
        self.assertRedirects(
            self.client.get(f'/task/{task.pk}/material/'),
            f'/login/?next=/task/{task.pk}/material/',
        )

        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(f'/task/{task.pk}/material/').status_code,
            404,
        )


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DeadlineReminderCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='reminder-owner',
            email='student@example.com',
            password='test-password',
        )
        self.task = Task.objects.create(
            user=self.user,
            title='Nộp bài Python',
            deadline=timezone.now() + timedelta(hours=2),
            estimated_minutes=60,
        )

    def test_dry_run_displays_reminder_without_sending_or_marking_it(self):
        output = io.StringIO()

        call_command(
            'send_deadline_reminders',
            dry_run=True,
            stdout=output,
        )

        self.assertIn('student@example.com', output.getvalue())
        self.assertIn('Nộp bài Python', output.getvalue())
        self.assertEqual(len(mail.outbox), 0)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.reminder_sent_for)

    def test_reminder_is_sent_once_and_only_for_eligible_tasks(self):
        completed_task = Task.objects.create(
            user=self.user,
            title='Đã hoàn thành',
            deadline=timezone.now() + timedelta(hours=1),
            estimated_minutes=30,
            status='completed',
        )
        foreign_user = User.objects.create_user(
            username='foreign-reminder-owner',
            email='foreign@example.com',
        )
        Task.objects.create(
            user=foreign_user,
            title='Nhiệm vụ của người khác',
            deadline=timezone.now() + timedelta(hours=1),
            estimated_minutes=30,
        )

        call_command('send_deadline_reminders', verbosity=0)
        call_command('send_deadline_reminders', verbosity=0)

        self.assertEqual(len(mail.outbox), 2)
        self.assertCountEqual(
            [message.to[0] for message in mail.outbox],
            ['student@example.com', 'foreign@example.com'],
        )
        self.assertIn(
            'Nộp bài Python',
            next(
                message.subject
                for message in mail.outbox
                if message.to == ['student@example.com']
            ),
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.reminder_sent_for, self.task.deadline)
        completed_task.refresh_from_db()
        self.assertIsNone(completed_task.reminder_sent_for)

    def test_reminder_skips_users_without_email(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])
        output = io.StringIO()

        call_command(
            'send_deadline_reminders',
            stderr=output,
            verbosity=0,
        )

        self.assertIn('has no email', output.getvalue())
        self.assertEqual(len(mail.outbox), 0)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.reminder_sent_for)

    def test_changed_deadline_can_be_reminded_again(self):
        call_command('send_deadline_reminders', verbosity=0)
        self.task.deadline = timezone.now() + timedelta(hours=3)
        self.task.save(update_fields=['deadline'])

        call_command('send_deadline_reminders', verbosity=0)

        self.assertEqual(len(mail.outbox), 2)
        self.task.refresh_from_db()
        self.assertEqual(self.task.reminder_sent_for, self.task.deadline)


class AuthenticationAndSeedTests(TestCase):
    def test_login_page_authenticates_registered_user(self):
        user = User.objects.create_user(
            username='student',
            password='test-password'
        )

        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            '/login/',
            {'username': 'student', 'password': 'test-password'}
        )

        self.assertRedirects(response, '/')
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            user.pk
        )

    def test_seed_command_is_repeatable_for_existing_user(self):
        user = User.objects.create_user(
            username='student',
            password='test-password'
        )

        call_command('seed_demo_data', username=user.username)
        call_command('seed_demo_data', username=user.username)

        self.assertEqual(Course.objects.filter(user=user).count(), 4)
        self.assertEqual(Task.objects.filter(user=user).count(), 8)
        self.assertEqual(RecurringSchedule.objects.filter(user=user).count(), 5)
        self.assertEqual(ScheduleBlock.objects.filter(user=user).count(), 2)

    def test_seed_command_requires_an_existing_user(self):
        with self.assertRaises(CommandError):
            call_command('seed_demo_data')

        self.assertEqual(User.objects.count(), 0)


class DeadlineAndCalendarCrudTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='owner',
            password='test-password'
        )
        self.other_user = User.objects.create_user(
            username='other-owner',
            password='test-password'
        )
        self.course = Course.objects.create(
            user=self.user,
            code='PY101',
            name='Lập trình Python'
        )
        self.task = Task.objects.create(
            user=self.user,
            course=self.course,
            title='Bài tập cũ',
            subject_name=self.course.name,
            deadline=timezone.now() + timedelta(days=2),
            estimated_minutes=60,
        )
        self.block = ScheduleBlock.objects.create(
            user=self.user,
            task=self.task,
            title='Ôn tập',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, minutes=60),
            status='confirmed',
        )
        self.client.force_login(self.user)

    def test_task_deadline_can_be_edited_and_is_owner_scoped(self):
        response = self.client.get(
            f'/task/{self.task.pk}/edit/'
        )
        self.assertEqual(response.status_code, 200)

        updated_deadline = timezone.localtime() + timedelta(days=4)
        response = self.client.post(
            f'/task/{self.task.pk}/edit/',
            {
                'title': 'Bài tập đã sửa',
                'course': str(self.course.pk),
                'subject_name': self.course.name,
                'deadline': updated_deadline.strftime('%Y-%m-%dT%H:%M'),
                'estimated_minutes': '90',
                'priority': '1',
                'material_url': '',
            }
        )
        self.assertRedirects(response, '/')
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Bài tập đã sửa')
        self.assertEqual(self.task.estimated_minutes, 90)

        foreign_task = Task.objects.create(
            user=self.other_user,
            title='Không thuộc tài khoản',
            deadline=timezone.now() + timedelta(days=1),
            estimated_minutes=30,
        )
        response = self.client.get(
            f'/task/{foreign_task.pk}/edit/'
        )
        self.assertEqual(response.status_code, 404)

    def test_task_toggle_and_delete_require_post(self):
        response = self.client.get(
            f'/task/{self.task.pk}/toggle/'
        )
        self.assertEqual(response.status_code, 405)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'todo')

        response = self.client.post(
            f'/task/{self.task.pk}/toggle/'
        )
        self.assertRedirects(response, '/')
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'completed')

        response = self.client.post(
            f'/task/{self.task.pk}/delete/'
        )
        self.assertRedirects(response, '/')
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())

    def test_schedule_block_form_rejects_end_before_start(self):
        start = timezone.localtime() + timedelta(days=1)
        form = ScheduleBlockForm(
            data={
                'title': 'Thời gian không hợp lệ',
                'task': '',
                'start_time': (start + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
                'end_time': (start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('end_time', form.errors)

    def test_drag_update_requires_csrf_and_only_updates_owned_events(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get('/calendar/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Xuất lịch .ics')
        self.assertNotContains(response, 'NOTPROVIDED')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        csrf_token = response.cookies['csrftoken'].value

        updated_start = timezone.localtime() + timedelta(days=2)
        payload = {
            'id': f'block-{self.block.pk}',
            'start': updated_start.isoformat(),
            'end': (updated_start + timedelta(hours=1)).isoformat(),
        }
        invalid_payload = {
            **payload,
            'end': (updated_start - timedelta(hours=1)).isoformat(),
        }
        response = client.post(
            '/api/update-block-time/',
            data=json.dumps(invalid_payload),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 400)

        response = client.post(
            '/api/update-block-time/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

        response = client.post(
            '/api/update-block-time/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 200)
        self.block.refresh_from_db()
        self.assertEqual(self.block.start_time, updated_start)

        foreign_block = ScheduleBlock.objects.create(
            user=self.other_user,
            title='Sự kiện của tài khoản khác',
            start_time=updated_start,
            end_time=updated_start + timedelta(hours=1),
        )
        payload['id'] = f'block-{foreign_block.pk}'
        response = client.post(
            '/api/update-block-time/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 404)

    def test_schedule_block_create_edit_delete_and_owner_scope(self):
        start = timezone.localtime() + timedelta(days=3)
        response = self.client.post(
            '/calendar/events/new/',
            {
                'title': 'Sự kiện mới',
                'task': str(self.task.pk),
                'start_time': start.strftime('%Y-%m-%dT%H:%M'),
                'end_time': (start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            }
        )
        self.assertRedirects(response, '/calendar/')
        created_block = ScheduleBlock.objects.get(title='Sự kiện mới')
        self.assertEqual(created_block.user, self.user)
        self.assertFalse(created_block.is_fixed)

        response = self.client.post(
            f'/calendar/events/{created_block.pk}/edit/',
            {
                'title': 'Sự kiện đã sửa',
                'task': str(self.task.pk),
                'start_time': (start + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
                'end_time': (start + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'),
            }
        )
        self.assertRedirects(response, '/calendar/')
        created_block.refresh_from_db()
        self.assertEqual(created_block.title, 'Sự kiện đã sửa')

        response = self.client.get(
            f'/calendar/events/{self.block.pk}/edit/'
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            f'/calendar/events/{self.block.pk}/delete/'
        )
        self.assertEqual(response.status_code, 405)

        response = self.client.post(
            f'/calendar/events/{created_block.pk}/delete/'
        )
        self.assertRedirects(response, '/calendar/')
        self.assertFalse(
            ScheduleBlock.objects.filter(pk=created_block.pk).exists()
        )

        self.client.force_login(self.other_user)
        response = self.client.get(
            f'/calendar/events/{self.block.pk}/edit/'
        )
        self.assertEqual(response.status_code, 404)


class CalendarIcsExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='calendar-owner',
            password='test-password'
        )
        self.other_user = User.objects.create_user(
            username='other-calendar-owner',
            password='test-password'
        )
        self.client.force_login(self.user)

    def test_export_contains_owned_deadlines_events_and_valid_folding(self):
        deadline = timezone.now() + timedelta(days=2)
        title = 'Bài tập; Python, phần 1\r\nSUMMARY:Injected'
        task = Task.objects.create(
            user=self.user,
            title=title,
            deadline=deadline,
            estimated_minutes=60,
            material_url='https://example.com/study',
        )
        ScheduleBlock.objects.create(
            user=self.user,
            task=task,
            title='Ôn tập ' + ('rất dài ' * 20),
            start_time=deadline - timedelta(hours=2),
            end_time=deadline - timedelta(hours=1),
            status='confirmed',
        )
        Task.objects.create(
            user=self.other_user,
            title='Không được xuất',
            deadline=deadline,
            estimated_minutes=30,
        )

        response = self.client.get('/calendar/export.ics')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar; charset=utf-8')
        self.assertIn('attachment; filename="ai-study-planner.ics"', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')

        calendar_text = response.content.decode('utf-8')
        self.assertTrue(calendar_text.startswith('BEGIN:VCALENDAR\r\n'))
        self.assertTrue(calendar_text.endswith('END:VCALENDAR\r\n'))
        self.assertEqual(calendar_text.count('BEGIN:VEVENT'), 2)
        self.assertIn(f'UID:task-{task.pk}@ai-study-planner.local', calendar_text)
        self.assertIn('SUMMARY:Deadline: Bài tập\\; Python\\, phần 1\\nSUMMARY:Injected', calendar_text)
        self.assertIn('https://example.com/study', calendar_text)
        self.assertNotIn('Không được xuất', calendar_text)
        self.assertTrue(
            all(
                len(line.encode('utf-8')) <= 75
                for line in calendar_text.split('\r\n')
            )
        )

    def test_export_requires_login(self):
        self.client.logout()

        response = self.client.get('/calendar/export.ics')

        self.assertRedirects(
            response,
            '/login/?next=/calendar/export.ics'
        )


# ============================================================
# TASK 3 - THUẬT TOÁN SINH KẾ HOẠCH TUẦN
# ============================================================

from datetime import datetime as _dt, time as _time, timezone as _dt_timezone  # noqa: E402

from .models import RecurringSchedule, UserProfile, PomodoroLog  # noqa: E402
from .risk import calculate_risk, assess_task  # noqa: E402
from .scheduler import (  # noqa: E402
    PlanTask, compute_free_slots, generate_weekly_plan, plan_sessions,
)


def _aware(day, hour, minute=0):
    return timezone.make_aware(_dt.combine(day, _time(hour, minute)))


class PlanSessionsUnitTests(TestCase):
    def setUp(self):
        self.day = timezone.localdate() + timedelta(days=1)

    def test_higher_priority_is_scheduled_first(self):
        slots = [[_aware(self.day, 8), _aware(self.day, 10, 30)]]
        low = PlanTask('low', 'Thấp', 60, _aware(self.day + timedelta(days=3), 0), 3)
        high = PlanTask('high', 'Cao', 60, _aware(self.day + timedelta(days=3), 0), 1)
        sessions, unscheduled = plan_sessions([low, high], slots)
        self.assertEqual([s.task.key for s in sessions], ['high', 'low'])
        self.assertEqual(unscheduled, {})

    def test_long_task_is_split_into_max_90_minute_sessions_with_breaks(self):
        slots = [[_aware(self.day, 8), _aware(self.day, 12)]]
        task = PlanTask('t', 'Dài', 150, _aware(self.day + timedelta(days=2), 0))
        sessions, _ = plan_sessions([task], slots)
        self.assertEqual([s.minutes for s in sessions], [90, 60])
        self.assertEqual(sessions[1].start - sessions[0].end, timedelta(minutes=10))

    def test_no_tiny_leftover_session(self):
        slots = [[_aware(self.day, 8), _aware(self.day, 12)]]
        task = PlanTask('t', 'Lẻ', 100, _aware(self.day + timedelta(days=2), 0))
        sessions, _ = plan_sessions([task], slots)
        self.assertEqual([s.minutes for s in sessions], [75, 25])

    def test_daily_study_cap_spreads_work_across_days(self):
        next_day = self.day + timedelta(days=1)
        slots = [
            [_aware(self.day, 6), _aware(self.day, 22)],
            [_aware(next_day, 6), _aware(next_day, 22)],
        ]
        task = PlanTask('t', 'Lớn', 360, _aware(self.day + timedelta(days=3), 0))
        sessions, unscheduled = plan_sessions([task], slots)
        self.assertEqual(unscheduled, {})
        first_day = sum(s.minutes for s in sessions if timezone.localtime(s.start).date() == self.day)
        self.assertEqual(first_day, 240)

    def test_session_never_ends_after_deadline(self):
        slots = [[_aware(self.day, 8), _aware(self.day, 12)]]
        task = PlanTask('t', 'Gấp', 120, _aware(self.day, 9))
        sessions, unscheduled = plan_sessions([task], slots)
        self.assertEqual(len(sessions), 1)
        self.assertLessEqual(sessions[0].end, task.deadline)
        self.assertEqual(unscheduled, {'t': 60})

    def test_urgent_low_priority_task_still_uses_earlier_free_slot(self):
        """Task ưu tiên cao nhưng hạn xa không được chiếm hết slot của task gấp."""
        slots = [
            [_aware(self.day, 8), _aware(self.day, 9)],
            [_aware(self.day, 14), _aware(self.day, 18)],
        ]
        far_high = PlanTask('far', 'Xa', 60, _aware(self.day + timedelta(days=5), 0), 1)
        urgent_low = PlanTask('urgent', 'Gấp', 60, _aware(self.day, 16), 3)
        sessions, unscheduled = plan_sessions([far_high, urgent_low], slots)
        self.assertEqual(unscheduled, {})
        urgent = [s for s in sessions if s.task.key == 'urgent'][0]
        self.assertLessEqual(urgent.end, urgent_low.deadline)

    def test_free_slots_skip_busy_blocks_and_sleep(self):
        now = _aware(self.day - timedelta(days=1), 23, 30)
        busy = [(_aware(self.day, 8), _aware(self.day, 11))]
        slots = compute_free_slots(busy, self.day, 0, _time(6, 0), _time(23, 0), now)
        self.assertEqual(slots, [
            [_aware(self.day, 6), _aware(self.day, 8)],
            [_aware(self.day, 11), _aware(self.day, 23)],
        ])


class WeeklyPlanIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('planner', password='pass12345')
        call_command('seed_demo_data', username='planner', stdout=io.StringIO())

    def test_generates_plan_from_eight_sample_tasks_without_overlap(self):
        self.assertEqual(Task.objects.filter(user=self.user).count(), 8)
        result = generate_weekly_plan(self.user)
        self.assertGreater(result['created'], 0)

        blocks = list(ScheduleBlock.objects.filter(user=self.user))
        suggested = [b for b in blocks if b.status == 'suggested']
        for block in suggested:
            self.assertLessEqual(block.end_time, block.task.deadline)
            self.assertLessEqual(block.end_time - block.start_time, timedelta(minutes=90))
            for other in blocks:
                if other.pk != block.pk:
                    overlaps = block.start_time < other.end_time and other.start_time < block.end_time
                    self.assertFalse(overlaps, f'{block} chồng {other}')

    def test_regenerating_keeps_user_edited_blocks(self):
        generate_weekly_plan(self.user)
        edited = ScheduleBlock.objects.filter(user=self.user, status='suggested').first()
        edited.status = 'confirmed'
        edited.save()
        generate_weekly_plan(self.user)
        self.assertTrue(ScheduleBlock.objects.filter(pk=edited.pk).exists())

    def test_auto_schedule_requires_post_and_login(self):
        self.assertEqual(Client().post('/auto-schedule/').status_code, 302)
        client = Client()
        client.force_login(self.user)
        self.assertEqual(client.get('/auto-schedule/').status_code, 405)
        self.assertRedirects(client.post('/auto-schedule/'), '/calendar/')


# ============================================================
# TASK 5 - ĐIỂM RỦI RO TRỄ HẠN
# ============================================================

class RiskScoreTests(TestCase):
    def test_completed_task_has_zero_risk(self):
        self.assertEqual(calculate_risk(hours_left=5, estimated_minutes=60, status='completed').score, 0)

    def test_overdue_task_has_max_risk(self):
        result = calculate_risk(hours_left=-1, estimated_minutes=60)
        self.assertEqual((result.score, result.level), (100, 'high'))

    def test_near_deadline_large_task_is_high_risk(self):
        result = calculate_risk(hours_left=6, estimated_minutes=300, priority=1)
        self.assertEqual(result.level, 'high')
        self.assertTrue(result.reasons)

    def test_far_deadline_small_task_is_low_risk(self):
        result = calculate_risk(hours_left=24 * 10, estimated_minutes=60,
                                scheduled_minutes=60, priority=3)
        self.assertEqual(result.level, 'low')

    def test_focus_time_and_scheduling_reduce_risk(self):
        base = calculate_risk(hours_left=30, estimated_minutes=240)
        better = calculate_risk(hours_left=30, estimated_minutes=240,
                                focused_minutes=120, scheduled_minutes=120)
        self.assertLess(better.score, base.score)

    def test_assess_task_uses_pomodoro_and_blocks(self):
        user = User.objects.create_user('risk', password='pass12345')
        now = timezone.now()
        task = Task.objects.create(user=user, title='Báo cáo', deadline=now + timedelta(hours=10),
                                   estimated_minutes=120, priority=1)
        before = assess_task(task, now)
        PomodoroLog.objects.create(user=user, task=task, status='completed', actual_seconds=3600)
        ScheduleBlock.objects.create(user=user, task=task, title='Học',
                                     start_time=now + timedelta(hours=1),
                                     end_time=now + timedelta(hours=2))
        after = assess_task(task, now)
        self.assertEqual(after.remaining_minutes, 60)
        self.assertLess(after.score, before.score)

    @override_settings(AI_BASE_URL='', GEMINI_API_KEY='', OPENAI_API_KEY='')
    def test_risk_api_and_ai_page_show_scores(self):
        user = User.objects.create_user('riskapi', password='pass12345')
        Task.objects.create(user=user, title='Gần hạn', deadline=timezone.now() + timedelta(hours=3),
                            estimated_minutes=200, priority=1)
        client = Client()
        client.force_login(user)
        data = client.get('/api/risk/').json()['tasks']
        self.assertEqual(data[0]['level'], 'high')
        page = client.get('/ai-assistant/')
        self.assertContains(page, 'Gần hạn')
        self.assertContains(page, 'Rủi ro cao')


# ============================================================
# TASK 2 - ĐỒNG BỘ .ICS VÀ NHẮC VIỆC
# ============================================================

class IcsSyncAndReminderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sync', email='s@example.com', password='pass12345')
        self.client.force_login(self.user)

    def test_subscription_feed_works_without_login_only_with_valid_token(self):
        profile = UserProfile.objects.create(user=self.user)
        Task.objects.create(user=self.user, title='Deadline feed',
                            deadline=timezone.now() + timedelta(days=1), estimated_minutes=30)
        anonymous = Client()
        response = anonymous.get(f'/calendar/feed/{profile.calendar_token}.ics')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Deadline feed', response.content.decode())
        missing = anonymous.get('/calendar/feed/00000000-0000-0000-0000-000000000000.ics')
        self.assertEqual(missing.status_code, 404)

    def test_import_ics_creates_fixed_busy_blocks(self):
        start = (timezone.now() + timedelta(days=2)).astimezone(_dt_timezone.utc)
        stamp = start.strftime('%Y%m%dT%H%M%SZ')
        end = (start + timedelta(hours=2)).strftime('%Y%m%dT%H%M%SZ')
        ics = (
            'BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:1\r\n'
            f'DTSTART:{stamp}\r\nDTEND:{end}\r\nSUMMARY:Thi giữa kỳ\\, phòng A1\r\n'
            'END:VEVENT\r\nEND:VCALENDAR\r\n'
        )
        upload = SimpleUploadedFile('lich.ics', ics.encode(), content_type='text/calendar')
        response = self.client.post('/calendar/import/', {'ics_file': upload})
        self.assertRedirects(response, '/calendar/')
        block = ScheduleBlock.objects.get(user=self.user)
        self.assertTrue(block.is_fixed)
        self.assertEqual(block.title, 'Lịch nhập: Thi giữa kỳ, phòng A1')
        self.assertEqual(block.end_time - block.start_time, timedelta(hours=2))

    def test_navbar_shows_in_app_reminder_for_upcoming_deadline(self):
        Task.objects.create(user=self.user, title='Sắp hết hạn',
                            deadline=timezone.now() + timedelta(hours=5), estimated_minutes=30)
        response = self.client.get('/')
        self.assertEqual(response.context['reminder_count'], 1)
        self.assertContains(response, 'Sắp hết hạn')

    def test_celery_task_runs_reminder_command(self):
        from .tasks import send_deadline_reminders_task
        Task.objects.create(user=self.user, title='Nhắc qua Celery',
                            deadline=timezone.now() + timedelta(hours=2), estimated_minutes=30)
        output = send_deadline_reminders_task.delay().get()
        self.assertIn('Sent: 1', output)
        self.assertEqual(len(mail.outbox), 1)


class RecurringOwnershipTests(TestCase):
    def test_user_cannot_delete_other_users_recurring_schedule(self):
        owner = User.objects.create_user('owner', password='pass12345')
        other = User.objects.create_user('other', password='pass12345')
        rec = RecurringSchedule.objects.create(user=owner, title='Lớp', day_of_week=0,
                                               start_time=_time(7), end_time=_time(9))
        client = Client()
        client.force_login(other)
        self.assertEqual(client.post(f'/recurring/{rec.id}/delete/').status_code, 404)
        self.assertEqual(client.get(f'/recurring/{rec.id}/delete/').status_code, 405)
        self.assertTrue(RecurringSchedule.objects.filter(pk=rec.pk).exists())


class FastApiAuxiliaryTests(TestCase):
    def test_risk_and_plan_endpoints(self):
        from fastapi.testclient import TestClient
        from .fastapi_app import api

        client = TestClient(api)
        self.assertEqual(client.get('/health').json(), {'status': 'ok'})
        risk = client.post('/risk', json={'hours_left': 4, 'estimated_minutes': 240, 'priority': 1}).json()
        self.assertEqual(risk['level'], 'high')

        day = timezone.localdate() + timedelta(days=1)
        plan = client.post('/plan', json={
            'tasks': [{'title': 'A', 'minutes': 120, 'deadline': _aware(day, 23).isoformat()}],
            'free_slots': [{'start': _aware(day, 8).isoformat(), 'end': _aware(day, 12).isoformat()}],
        }).json()
        self.assertEqual([s['minutes'] for s in plan['sessions']], [90, 30])


class UserRoleAndProfileTests(TestCase):
    """Phân quyền Quản trị viên / Sinh viên, quản lý user và hồ sơ cá nhân."""

    def setUp(self):
        self.admin = User.objects.create_user(username='quantri', password='Admin-pass-123', is_staff=True)
        self.student = User.objects.create_user(username='sinhvien', password='Student-pass-123')
        self.other = User.objects.create_user(username='banhoc', password='Other-pass-123')

    def test_student_cannot_open_user_management(self):
        self.client.force_login(self.student)
        response = self.client.get('/manage/users/')
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'không có quyền', status_code=403)

    def test_anonymous_is_redirected_to_login_with_next(self):
        response = self.client.get('/manage/users/')
        self.assertRedirects(response, '/login/?next=/manage/users/', fetch_redirect_response=False)

    def test_admin_sees_user_list_and_can_search(self):
        self.client.force_login(self.admin)
        response = self.client.get('/manage/users/', {'q': 'sinhvien'})
        self.assertEqual(response.status_code, 200)
        usernames = [u.username for u in response.context['page'].object_list]
        self.assertEqual(usernames, ['sinhvien'])
        self.assertEqual(response.context['stats']['total'], 3)
        self.assertEqual(response.context['stats']['admins'], 1)

    def test_admin_locks_user_and_locked_user_cannot_log_in(self):
        self.client.force_login(self.admin)
        self.client.post(f'/manage/users/{self.student.id}/toggle-active/')
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

        self.assertFalse(Client().login(username='sinhvien', password='Student-pass-123'))

        self.client.post(f'/manage/users/{self.student.id}/toggle-active/')
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)

    def test_admin_grants_and_revokes_admin_role(self):
        self.client.force_login(self.admin)
        self.client.post(f'/manage/users/{self.other.id}/toggle-staff/')
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_staff)
        self.client.post(f'/manage/users/{self.other.id}/toggle-staff/')
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_staff)

    def test_admin_cannot_lock_or_demote_self(self):
        self.client.force_login(self.admin)
        self.client.post(f'/manage/users/{self.admin.id}/toggle-active/')
        self.client.post(f'/manage/users/{self.admin.id}/toggle-staff/')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertTrue(self.admin.is_staff)

    def test_staff_cannot_change_superuser(self):
        root = User.objects.create_superuser(username='root', password='Root-pass-123')
        self.client.force_login(self.admin)
        self.client.post(f'/manage/users/{root.id}/toggle-active/')
        root.refresh_from_db()
        self.assertTrue(root.is_active)

    def test_student_cannot_call_management_actions(self):
        self.client.force_login(self.student)
        response = self.client.post(f'/manage/users/{self.other.id}/toggle-staff/')
        self.assertEqual(response.status_code, 403)
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_staff)

    def test_management_actions_require_post(self):
        self.client.force_login(self.admin)
        response = self.client.get(f'/manage/users/{self.student.id}/toggle-active/')
        self.assertEqual(response.status_code, 405)

    def test_profile_updates_name_but_not_username(self):
        self.student.email = 'an@example.com'
        self.student.save()
        self.client.force_login(self.student)

        self.client.post('/profile/', {
            'form': 'profile', 'last_name': 'Nguyễn', 'first_name': 'An',
            'email': 'an@example.com', 'username': 'ten_moi',
        })
        self.student.refresh_from_db()
        self.assertEqual(self.student.get_full_name(), 'An Nguyễn')
        self.assertEqual(self.student.username, 'sinhvien')
        self.assertEqual(len(mail.outbox), 0)

    def test_change_password_keeps_session(self):
        self.client.force_login(self.student)
        response = self.client.post('/profile/', {
            'form': 'password',
            'old_password': 'Student-pass-123',
            'new_password1': 'Moi-mat-khau-456',
            'new_password2': 'Moi-mat-khau-456',
        })
        self.assertRedirects(response, '/profile/')
        self.assertEqual(self.client.get('/profile/').status_code, 200)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password('Moi-mat-khau-456'))

    def test_logout_requires_post(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/logout/').status_code, 405)
        self.client.post('/logout/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_redirects_to_safe_next_only(self):
        response = self.client.post('/login/?next=/calendar/', {
            'username': 'sinhvien', 'password': 'Student-pass-123', 'next': '/calendar/',
        })
        self.assertRedirects(response, '/calendar/', fetch_redirect_response=False)

        self.client.logout()
        response = self.client.post('/login/', {
            'username': 'sinhvien', 'password': 'Student-pass-123', 'next': 'https://evil.example.com/',
        })
        self.assertRedirects(response, '/', fetch_redirect_response=False)


class EmailVerificationAndPasswordResetTests(TestCase):
    """Đăng ký 3 trường, xác thực email, quên mật khẩu (một email nhiều tài khoản)."""

    password = 'Hoc-tap-2026!'

    def register(self, username='an', email='An@Gmail.com'):
        return self.client.post('/register/', {
            'email': email, 'username': username, 'password': self.password,
        })

    def link_from_last_email(self):
        import re
        return re.search(r'http://testserver(/\S+)', mail.outbox[-1].body).group(1)

    def test_register_requires_only_three_fields_and_sends_verification(self):
        response = self.register()
        self.assertRedirects(response, '/verify-email/sent/')

        user = User.objects.get(username='an')
        self.assertEqual(user.email, 'an@gmail.com')
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(user.profile.email_verified)
        self.assertNotIn('_auth_user_id', self.client.session)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['an@gmail.com'])
        self.assertIn('/verify-email/', mail.outbox[0].body)
        self.assertIn('text/html', [m for _, m in mail.outbox[0].alternatives])

    def test_register_rejects_weak_password_and_duplicate_username(self):
        response = self.client.post('/register/', {'email': 'a@b.com', 'username': 'an', 'password': '123'})
        self.assertFalse(User.objects.filter(username='an').exists())
        self.assertTrue(response.context['form'].errors['password'])

        User.objects.create_user(username='an', password=self.password)
        response = self.register()
        self.assertIn('đã có người dùng', str(response.context['form'].errors['username']))

    def test_one_email_can_have_many_accounts(self):
        self.register('an', 'chung@gmail.com')
        self.register('binh', 'chung@gmail.com')
        self.assertEqual(User.objects.filter(email='chung@gmail.com').count(), 2)

    def test_unverified_user_cannot_log_in_until_link_clicked(self):
        self.register()
        verify_path = self.link_from_last_email()

        response = self.client.post('/login/', {'username': 'an', 'password': self.password})
        self.assertRedirects(response, '/verify-email/sent/')
        self.assertNotIn('_auth_user_id', self.client.session)

        response = self.client.get(verify_path)
        self.assertRedirects(response, '/login/?username=an', fetch_redirect_response=False)
        self.assertTrue(User.objects.get(username='an').profile.email_verified)

        response = self.client.post('/login/', {'username': 'an', 'password': self.password})
        self.assertRedirects(response, '/')

        # Link đã dùng thì hết hiệu lực
        self.client.post('/logout/')
        response = self.client.get(verify_path, follow=True)
        self.assertContains(response, 'không hợp lệ hoặc đã hết hạn')

    def test_wrong_password_on_unverified_account_shows_generic_error(self):
        self.register()
        response = self.client.post('/login/', {'username': 'an', 'password': 'sai-mat-khau'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'không chính xác')

    def test_resend_verification_has_cooldown(self):
        self.register()
        self.client.post('/verify-email/resend/')
        self.assertEqual(len(mail.outbox), 1)

        session = self.client.session
        session['verification_sent_at'] = 0
        session.save()
        self.client.post('/verify-email/resend/')
        self.assertEqual(len(mail.outbox), 2)

    def test_existing_and_admin_created_users_stay_verified(self):
        user = User.objects.create_user(username='cu', password=self.password)
        self.assertTrue(self.client.login(username='cu', password=self.password))
        self.assertTrue(UserProfile.objects.get_or_create(user=user)[0].email_verified)

    def test_password_reset_sends_one_email_per_account_with_username(self):
        for name in ['an', 'binh']:
            User.objects.create_user(username=name, email='chung@gmail.com', password=self.password)
        User.objects.create_user(username='khac', email='khac@gmail.com', password=self.password)

        response = self.client.post('/password-reset/', {'email': 'CHUNG@gmail.com'})
        self.assertRedirects(response, '/password-reset/sent/')
        self.assertEqual(len(mail.outbox), 2)
        bodies = ' '.join(m.body for m in mail.outbox)
        self.assertIn('Tên đăng nhập: an', bodies)
        self.assertIn('Tên đăng nhập: binh', bodies)
        self.assertNotIn('khac', bodies)

    def test_password_reset_sets_new_password_and_verifies_email(self):
        self.register()
        mail.outbox.clear()
        self.client.post('/password-reset/', {'email': 'an@gmail.com'})
        reset_path = self.link_from_last_email()

        response = self.client.get(reset_path, follow=True)
        form_url = response.redirect_chain[-1][0]
        response = self.client.post(form_url, {
            'new_password1': 'Mat-khau-moi-789', 'new_password2': 'Mat-khau-moi-789',
        })
        self.assertRedirects(response, '/reset/done/')

        user = User.objects.get(username='an')
        self.assertTrue(user.check_password('Mat-khau-moi-789'))
        self.assertTrue(user.profile.email_verified)

    def test_unknown_email_reset_does_not_reveal_anything(self):
        response = self.client.post('/password-reset/', {'email': 'khongco@gmail.com'})
        self.assertRedirects(response, '/password-reset/sent/')
        self.assertEqual(len(mail.outbox), 0)

    def test_changing_email_requires_confirmation_link(self):
        user = User.objects.create_user(username='an', email='cu@gmail.com', password=self.password)
        self.client.force_login(user)

        self.client.post('/profile/', {'form': 'profile', 'last_name': '', 'first_name': 'An', 'email': 'moi@gmail.com'})
        user.refresh_from_db()
        self.assertEqual(user.email, 'cu@gmail.com')
        self.assertEqual(user.profile.pending_email, 'moi@gmail.com')
        self.assertEqual(mail.outbox[-1].to, ['moi@gmail.com'])

        self.client.get(self.link_from_last_email())
        user.refresh_from_db()
        self.assertEqual(user.email, 'moi@gmail.com')
        self.assertEqual(user.profile.pending_email, '')

    def test_cancel_pending_email_invalidates_link(self):
        user = User.objects.create_user(username='an', email='cu@gmail.com', password=self.password)
        self.client.force_login(user)
        self.client.post('/profile/', {'form': 'profile', 'last_name': '', 'first_name': '', 'email': 'moi@gmail.com'})
        link = self.link_from_last_email()
        self.client.post('/profile/', {'form': 'cancel_email'})
        self.client.get(link)
        user.refresh_from_db()
        self.assertEqual(user.email, 'cu@gmail.com')


class BrevoBackendTests(TestCase):
    def test_payload_and_request(self):
        from unittest import mock
        from django.core.mail import EmailMultiAlternatives
        from .email_backends import BrevoApiBackend

        message = EmailMultiAlternatives(
            'Tiêu đề', 'Nội dung', 'StudyPlanner <noreply@studyplanner.vn>', ['An <an@gmail.com>'],
        )
        message.attach_alternative('<b>Nội dung</b>', 'text/html')

        response = mock.MagicMock()
        response.read.return_value = b'{"messageId": "abc"}'
        response.__enter__.return_value = response
        with mock.patch('urllib.request.urlopen', return_value=response) as urlopen:
            sent = BrevoApiBackend(api_key='test-key').send_messages([message])

        self.assertEqual(sent, 1)
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(request.get_header('Api-key'), 'test-key')
        payload = json.loads(request.data)
        self.assertEqual(payload['sender'], {'email': 'noreply@studyplanner.vn', 'name': 'StudyPlanner'})
        self.assertEqual(payload['to'], [{'email': 'an@gmail.com', 'name': 'An'}])
        self.assertEqual(payload['htmlContent'], '<b>Nội dung</b>')

    def test_missing_api_key_raises(self):
        from django.core.mail import EmailMessage
        from .email_backends import BrevoApiBackend

        with self.settings(BREVO_API_KEY=''):
            with self.assertRaises(RuntimeError):
                BrevoApiBackend().send_messages([EmailMessage('a', 'b', 'x@y.vn', ['z@y.vn'])])


class CalendarInviteTests(TestCase):
    """Lời mời lịch qua email: REQUEST khi tạo/sửa, CANCEL khi xóa/hoàn thành."""

    def setUp(self):
        self.user = User.objects.create_user(username='an', email='an@gmail.com', password='Hoc-tap-2026!')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.calendar_invites_enabled = True
        self.profile.save()
        self.deadline = timezone.now() + timedelta(days=2)

    def create_task(self, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return Task.objects.create(
                user=self.user, title='Báo cáo, đồ án; giữa kỳ', deadline=self.deadline,
                estimated_minutes=90, **extra,
            )

    def ics_of(self, message):
        ics = next(content for content, mimetype in message.alternatives if mimetype.startswith('text/calendar'))
        self.assertTrue(all(len(line.encode()) <= 75 for line in ics.split('\r\n')))
        return ics.replace('\r\n ', '')  # unfold dòng dài (RFC 5545)

    def test_new_task_sends_request_invite_with_attachment(self):
        task = self.create_task()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['an@gmail.com'])
        self.assertTrue(message.subject.startswith('Lời mời lịch: Deadline:'))
        ics = self.ics_of(message)
        self.assertIn('METHOD:REQUEST', ics)
        self.assertIn(f'UID:invite-task-{task.pk}@studyplanner', ics)
        self.assertIn('SEQUENCE:0', ics)
        self.assertIn('SUMMARY:Deadline: Báo cáo\, đồ án\; giữa kỳ', ics)
        self.assertIn('ATTENDEE;CN="an"', ics)
        self.assertIn('mailto:an@gmail.com', ics)
        self.assertEqual(message.attachments[0][0], 'invite.ics')

        task.refresh_from_db()
        self.assertEqual(task.invite_sequence, 0)

    def test_update_increments_sequence_only_when_content_changes(self):
        task = self.create_task()
        with self.captureOnCommitCallbacks(execute=True):
            task.estimated_minutes = 90
            task.save()
        self.assertEqual(len(mail.outbox), 1, 'Không đổi nội dung thì không gửi lại')

        with self.captureOnCommitCallbacks(execute=True):
            task.deadline = self.deadline + timedelta(hours=3)
            task.save()
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(mail.outbox[1].subject.startswith('Cập nhật lịch:'))
        self.assertIn('SEQUENCE:1', self.ics_of(mail.outbox[1]))

    def test_reminder_bookkeeping_save_does_not_send(self):
        task = self.create_task()
        with self.captureOnCommitCallbacks(execute=True):
            task.reminder_sent_for = task.deadline
            task.save(update_fields=['reminder_sent_for'])
        self.assertEqual(len(mail.outbox), 1)

    def test_completing_task_sends_cancel_and_reopening_sends_request(self):
        task = self.create_task()
        with self.captureOnCommitCallbacks(execute=True):
            task.status = 'completed'
            task.save()
        cancel = self.ics_of(mail.outbox[-1])
        self.assertIn('METHOD:CANCEL', cancel)
        self.assertIn('STATUS:CANCELLED', cancel)
        self.assertIn('SEQUENCE:1', cancel)

        with self.captureOnCommitCallbacks(execute=True):
            task.status = 'todo'
            task.save()
        reopened = self.ics_of(mail.outbox[-1])
        self.assertIn('METHOD:REQUEST', reopened)
        self.assertIn('SEQUENCE:2', reopened)

    def test_deleting_task_sends_cancel_with_same_uid(self):
        task = self.create_task()
        uid = f'UID:invite-task-{task.pk}@studyplanner'
        with self.captureOnCommitCallbacks(execute=True):
            task.delete()
        self.assertEqual(len(mail.outbox), 2)
        ics = self.ics_of(mail.outbox[1])
        self.assertIn('METHOD:CANCEL', ics)
        self.assertIn(uid, ics)

    def test_no_invites_when_disabled_or_unverified(self):
        self.profile.calendar_invites_enabled = False
        self.profile.save()
        self.create_task()
        self.assertEqual(len(mail.outbox), 0)

        self.profile.calendar_invites_enabled = True
        self.profile.email_verified = False
        self.profile.save()
        self.create_task()
        self.assertEqual(len(mail.outbox), 0)

    def test_only_confirmed_user_blocks_are_invited(self):
        start = timezone.now() + timedelta(days=1)
        with self.captureOnCommitCallbacks(execute=True):
            ScheduleBlock.objects.create(user=self.user, title='Lịch bận', start_time=start,
                                         end_time=start + timedelta(hours=1), is_fixed=True, status='confirmed')
            suggestion = ScheduleBlock.objects.create(user=self.user, title='Ôn tập: SQL', start_time=start,
                                                      end_time=start + timedelta(hours=1), status='suggested')
        self.assertEqual(len(mail.outbox), 0)

        # Kéo thả gợi ý -> thành 'confirmed' -> gửi lời mời
        with self.captureOnCommitCallbacks(execute=True):
            suggestion.status = 'confirmed'
            suggestion.save(update_fields=['status'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('TRANSP:OPAQUE', self.ics_of(mail.outbox[0]))

    def test_enable_in_profile_sends_upcoming_items(self):
        self.profile.calendar_invites_enabled = False
        self.profile.save()
        Task.objects.create(user=self.user, title='Sắp tới', deadline=self.deadline, estimated_minutes=60)
        Task.objects.create(user=self.user, title='Đã qua', deadline=timezone.now() - timedelta(days=1), estimated_minutes=60)
        Task.objects.create(user=self.user, title='Xong rồi', deadline=self.deadline, status='completed', estimated_minutes=60)

        self.client.force_login(self.user)
        response = self.client.post('/profile/', {'form': 'invites', 'enabled': '1'}, follow=True)
        self.assertContains(response, 'Đã bật lời mời lịch')
        self.assertEqual([m.subject.split(' (')[0] for m in mail.outbox], ['Lời mời lịch: Deadline: Sắp tới'])

        self.client.post('/profile/', {'form': 'invites', 'enabled': '0'})
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.calendar_invites_enabled)

    def test_cannot_enable_without_verified_email(self):
        self.profile.calendar_invites_enabled = False
        self.profile.email_verified = False
        self.profile.save()
        self.client.force_login(self.user)
        self.client.post('/profile/', {'form': 'invites', 'enabled': '1'})
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.calendar_invites_enabled)

    def test_brevo_payload_includes_ics_attachment(self):
        import base64
        from .email_backends import build_payload

        self.create_task()
        payload = build_payload(mail.outbox[0])
        self.assertEqual(payload['attachment'][0]['name'], 'invite.ics')
        self.assertIn(b'METHOD:REQUEST', base64.b64decode(payload['attachment'][0]['content']))


class AiProviderTests(TestCase):
    """AI hỗ trợ qua API chuẩn OpenAI: Ollama (Colab) / Gemini / OpenAI và phân tích dự phòng."""

    def setUp(self):
        self.user = User.objects.create_user('ai', password='pass12345')
        Task.objects.create(user=self.user, title='Đồ án', deadline=timezone.now() + timedelta(hours=5),
                            estimated_minutes=120, priority=1)

    @override_settings(AI_BASE_URL='https://abc.trycloudflare.com/v1', AI_API_KEY='', AI_MODEL='',
                       GEMINI_API_KEY='g-key', OPENAI_API_KEY='o-key')
    def test_ollama_base_url_has_priority(self):
        from .ai_assistant import get_ai_provider
        provider = get_ai_provider()
        self.assertEqual(provider['base_url'], 'https://abc.trycloudflare.com/v1')
        self.assertEqual(provider['api_key'], 'ollama')
        self.assertEqual(provider['model'], 'qwen2.5:7b')

    @override_settings(AI_BASE_URL='', AI_MODEL='', GEMINI_API_KEY='g-key', OPENAI_API_KEY='o-key')
    def test_gemini_uses_openai_compatible_endpoint(self):
        from .ai_assistant import GEMINI_OPENAI_BASE_URL, get_ai_provider
        provider = get_ai_provider()
        self.assertEqual(provider['base_url'], GEMINI_OPENAI_BASE_URL)
        self.assertEqual(provider['model'], 'gemini-flash-lite-latest')

    @override_settings(AI_BASE_URL='', GEMINI_API_KEY='', OPENAI_API_KEY='')
    def test_no_provider_uses_fallback_without_network(self):
        from .ai_assistant import analyze_schedule_with_ai
        result = analyze_schedule_with_ai(self.user)
        self.assertFalse(result['is_ai_generated'])
        self.assertIn('Đồ án', result['daily_summary'])

    @override_settings(AI_BASE_URL='http://localhost:11434/v1', AI_MODEL='qwen2.5:7b')
    def test_parses_json_wrapped_in_markdown_from_small_models(self):
        from unittest import mock
        from .ai_assistant import analyze_schedule_with_ai

        content = '```json\n{"daily_summary": "Học đồ án 19:00-21:00", "risk_warnings": "Đồ án gấp", "habit_advice": "Nghỉ 5 phút"}\n```'
        fake = mock.MagicMock()
        fake.chat.completions.create.return_value.choices = [mock.MagicMock(message=mock.MagicMock(content=content))]
        with mock.patch('openai.OpenAI', return_value=fake) as client_cls:
            result = analyze_schedule_with_ai(self.user)

        self.assertEqual(client_cls.call_args.kwargs['base_url'], 'http://localhost:11434/v1')
        self.assertTrue(result['is_ai_generated'])
        self.assertEqual(result['risk_warnings'], ['Đồ án gấp'])
        self.assertEqual(result['ai_provider'], 'Ollama/tùy chỉnh · qwen2.5:7b')

    @override_settings(AI_BASE_URL='http://localhost:9/v1', AI_TIMEOUT_SECONDS=1)
    def test_unreachable_server_falls_back_and_page_says_so(self):
        self.client.force_login(self.user)
        response = self.client.get('/ai-assistant/')
        self.assertContains(response, 'Không kết nối được AI')
        self.assertContains(response, 'Đồ án')


class CronReminderEndpointTests(TestCase):
    url = '/internal/cron/reminders/'

    def test_hidden_when_secret_not_configured(self):
        with self.settings(CRON_SECRET=''):
            self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_rejects_wrong_secret_and_get(self):
        with self.settings(CRON_SECRET='bi-mat'):
            self.assertEqual(self.client.post(self.url, HTTP_X_CRON_SECRET='sai').status_code, 403)
            self.assertEqual(self.client.get(self.url, HTTP_X_CRON_SECRET='bi-mat').status_code, 405)

    def test_sends_reminders_with_correct_secret(self):
        user = User.objects.create_user('cron', email='cron@example.com', password='pass12345')
        Task.objects.create(user=user, title='Sắp hạn', deadline=timezone.now() + timedelta(hours=2), estimated_minutes=30)
        with self.settings(CRON_SECRET='bi-mat'):
            response = self.client.post(self.url, HTTP_X_CRON_SECRET='bi-mat')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Sent: 1', response.json()['result'])
