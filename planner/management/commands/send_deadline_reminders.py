from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.db.models import F, Q
from django.utils import timezone

from planner.models import Task


class Command(BaseCommand):
    help = 'Send email reminders for unfinished tasks due within the next 24 hours.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours-before',
            type=int,
            default=24,
            help='Include deadlines within this many upcoming hours (default: 24).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List eligible reminders without sending email or updating tasks.',
        )

    def handle(self, *args, **options):
        hours_before = options['hours_before']
        if hours_before <= 0:
            raise CommandError('--hours-before must be a positive integer.')

        now = timezone.now()
        deadline_limit = now + timedelta(hours=hours_before)
        tasks = (
            Task.objects
            .filter(
                deadline__gt=now,
                deadline__lte=deadline_limit,
            )
            .exclude(status='completed')
            .filter(
                Q(reminder_sent_for__isnull=True)
                | ~Q(reminder_sent_for=F('deadline'))
            )
            .select_related('user')
            .order_by('deadline', 'pk')
        )

        processed = 0
        skipped = 0
        for task in tasks:
            if not task.user.email:
                self.stderr.write(
                    self.style.WARNING(
                        f'Skipped task #{task.pk}: user {task.user.username} has no email.'
                    )
                )
                skipped += 1
                continue

            deadline_text = timezone.localtime(task.deadline).strftime('%H:%M %d/%m/%Y')
            if options['dry_run']:
                self.stdout.write(
                    f'[DEMO] {task.user.email} | {task.title} | hạn {deadline_text}'
                )
                processed += 1
                continue

            sent_count = send_mail(
                subject=f'Nhắc hạn nộp: {task.title}',
                message=(
                    f'Xin chào {task.user.username},\n\n'
                    f'Nhiệm vụ "{task.title}" sắp đến hạn lúc {deadline_text}.\n'
                    'Hãy mở AI Study Planner để xem và cập nhật tiến độ.\n'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[task.user.email],
                fail_silently=False,
            )
            if sent_count != 1:
                raise CommandError(
                    f'Không gửi được email nhắc hạn cho nhiệm vụ #{task.pk}.'
                )

            task.reminder_sent_for = task.deadline
            task.save(update_fields=['reminder_sent_for'])
            self.stdout.write(
                self.style.SUCCESS(
                    f'Reminder sent for task #{task.pk} to {task.user.email}.'
                )
            )
            processed += 1

        mode = 'Demo' if options['dry_run'] else 'Sent'
        self.stdout.write(
            f'{mode}: {processed} reminder(s); skipped: {skipped}.'
        )
