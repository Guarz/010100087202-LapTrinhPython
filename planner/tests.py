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
from .models import Course, ScheduleBlock, Task


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
