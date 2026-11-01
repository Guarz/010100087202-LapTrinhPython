import uuid

from django.db import migrations, models


def generate_tokens(apps, schema_editor):
    UserProfile = apps.get_model('planner', 'UserProfile')
    for profile in UserProfile.objects.filter(calendar_token__isnull=True):
        profile.calendar_token = uuid.uuid4()
        profile.save(update_fields=['calendar_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0005_task_material_file_task_reminder_sent_for'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='calendar_token',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(generate_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='userprofile',
            name='calendar_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
