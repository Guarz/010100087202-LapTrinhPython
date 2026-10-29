import django.core.validators
from django.db import migrations, models
import planner.models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0004_course_task_course_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='material_file',
            field=models.FileField(
                blank=True,
                upload_to=planner.models.study_material_upload_path,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt']
                    ),
                    planner.models.validate_study_material_size,
                ],
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='reminder_sent_for',
            field=models.DateTimeField(
                blank=True,
                editable=False,
                null=True,
            ),
        ),
    ]
