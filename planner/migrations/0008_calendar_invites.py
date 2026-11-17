from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0007_userprofile_email_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='calendar_invites_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='task',
            name='invite_sequence',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='invite_hash',
            field=models.CharField(blank=True, default='', editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name='scheduleblock',
            name='invite_sequence',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='scheduleblock',
            name='invite_hash',
            field=models.CharField(blank=True, default='', editable=False, max_length=64),
        ),
    ]
