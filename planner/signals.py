# planner/signals.py
"""
Tự động gửi lời mời lịch qua email khi Task / ScheduleBlock thay đổi.

Chỉ đẩy job vào Celery sau khi transaction ghi DB thành công (on_commit),
và chỉ khi người dùng đã bật "Gửi lời mời lịch" trong Hồ sơ.
Tạo hàng loạt bằng bulk_create (lịch gợi ý của thuật toán) không phát
signal nên không sinh email.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import ScheduleBlock, Task, UserProfile

logger = logging.getLogger(__name__)

# Lưu các trường này không làm đổi nội dung sự kiện trên lịch
IGNORED_UPDATE_FIELDS = {'reminder_sent_for', 'invite_sequence', 'invite_hash'}


def _invites_enabled(user_id):
    return UserProfile.objects.filter(user_id=user_id, calendar_invites_enabled=True).exists()


def _enqueue(task, *args):
    def run():
        try:
            task.delay(*args)
        except Exception:
            # Không để lỗi broker/email làm hỏng thao tác lưu của người dùng
            logger.exception('Không đẩy được job lời mời lịch %s%s', task.name, args)
    transaction.on_commit(run)


def _on_save(kind, instance, update_fields):
    if update_fields and set(update_fields) <= IGNORED_UPDATE_FIELDS:
        return
    if not _invites_enabled(instance.user_id):
        return
    from .tasks import sync_calendar_invite_task
    _enqueue(sync_calendar_invite_task, kind, instance.pk)


def _on_delete(kind, instance):
    if not _invites_enabled(instance.user_id):
        return
    from .calendar_invites import CANCELLED_HASH, snapshot_for_cancel
    state = type(instance).objects.filter(pk=instance.pk).values('invite_sequence', 'invite_hash').first()
    if not state or state['invite_sequence'] is None or state['invite_hash'] == CANCELLED_HASH:
        return
    instance.invite_sequence = state['invite_sequence']
    from .tasks import cancel_calendar_invite_task
    _enqueue(cancel_calendar_invite_task, snapshot_for_cancel(instance, kind))


@receiver(post_save, sender=Task)
def task_saved(sender, instance, update_fields=None, **kwargs):
    _on_save('task', instance, update_fields)


@receiver(post_save, sender=ScheduleBlock)
def block_saved(sender, instance, update_fields=None, **kwargs):
    _on_save('block', instance, update_fields)


@receiver(pre_delete, sender=Task)
def task_deleted(sender, instance, **kwargs):
    _on_delete('task', instance)


@receiver(pre_delete, sender=ScheduleBlock)
def block_deleted(sender, instance, **kwargs):
    _on_delete('block', instance)
