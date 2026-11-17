from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0008_calendar_invites'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='theme',
            field=models.CharField(
                choices=[('indigo', 'Chàm'), ('violet', 'Tím học tập'), ('teal', 'Xanh ngọc'),
                         ('blue', 'Xanh dương'), ('orange', 'Cam năng lượng')],
                default='indigo', max_length=20,
            ),
        ),
    ]
