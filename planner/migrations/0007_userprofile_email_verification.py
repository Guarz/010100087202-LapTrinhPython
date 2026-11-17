from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0006_userprofile_calendar_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='email_verified',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='pending_email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
    ]
