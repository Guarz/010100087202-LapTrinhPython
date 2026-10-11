from django.contrib import admin
from .models import UserProfile, RecurringSchedule, Task, ScheduleBlock, PomodoroLog

admin.site.register(UserProfile)
admin.site.register(RecurringSchedule)
admin.site.register(Task)
admin.site.register(ScheduleBlock)
admin.site.register(PomodoroLog)