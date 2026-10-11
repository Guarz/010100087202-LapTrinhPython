from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    preferred_study_hours = models.CharField(max_length=50, default="19:00-22:00", help_text="VD: 19:00-22:00")
    sleep_hours = models.CharField(max_length=50, default="23:00-06:00", help_text="Giờ ngủ cố định")

    def __str__(self):
        return f"Hồ sơ của {self.user.username}"

class RecurringSchedule(models.Model):
    DAY_CHOICES = [
        (0, 'Thứ Hai'),
        (1, 'Thứ Ba'),
        (2, 'Thứ Tư'),
        (3, 'Thứ Năm'),
        (4, 'Thứ Sáu'),
        (5, 'Thứ Bảy'),
        (6, 'Chủ Nhật'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_schedules')
    title = models.CharField(max_length=150)
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    category = models.CharField(max_length=50, default="school") # school, part_time, personal

    def __str__(self):
        return f"{self.title} ({self.get_day_of_week_display()})"

class Task(models.Model):
    PRIORITY_CHOICES = [
        (1, 'Cao'),
        (2, 'Trung bình'),
        (3, 'Thấp'),
    ]
    STATUS_CHOICES = [
        ('todo', 'Chưa làm'),
        ('in_progress', 'Đang làm'),
        ('completed', 'Đã xong'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    subject_name = models.CharField(max_length=100, blank=True, null=True)
    deadline = models.DateTimeField()
    estimated_minutes = models.IntegerField(help_text="Thời lượng ước tính (phút)")
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    material_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class ScheduleBlock(models.Model):
    STATUS_CHOICES = [
        ('suggested', 'Được đề xuất'),
        ('confirmed', 'Đã xác nhận'),
        ('completed', 'Đã hoàn thành'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedule_blocks')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='blocks')
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_fixed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='suggested')

    def __str__(self):
        return f"{self.title} [{self.start_time.strftime('%d/%m %H:%M')}]"

class PomodoroLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pomodoro_logs')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField(auto_now_add=True)
    duration_minutes = models.IntegerField(default=25)
    completed = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.duration_minutes}m ({self.start_time.strftime('%d/%m')})"