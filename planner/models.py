
import uuid

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils import timezone


MAX_STUDY_MATERIAL_SIZE = 10 * 1024 * 1024


def study_material_upload_path(instance, filename):
    extension = filename.rpartition('.')[2].lower()
    safe_extension = (
        f'.{extension}'
        if extension.isalnum() and len(extension) <= 10
        else ''
    )
    return f'study_materials/user_{instance.user_id}/{uuid.uuid4().hex}{safe_extension}'


def validate_study_material_size(uploaded_file):
    if uploaded_file.size > MAX_STUDY_MATERIAL_SIZE:
        raise ValidationError('Tài liệu không được vượt quá 10 MB.')


# ============================================================
# 01. USER PROFILE
# GIỮ NGUYÊN - KHÔNG THUỘC PHẠM VI POMODORO
# ============================================================

class UserProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    preferred_study_hours = models.CharField(
        max_length=50,
        default="19:00-22:00",
        help_text="VD: 19:00-22:00"
    )

    sleep_hours = models.CharField(
        max_length=50,
        default="23:00-06:00",
        help_text="Giờ ngủ cố định"
    )

    def __str__(self):
        return f"Hồ sơ của {self.user.username}"


# ============================================================
# 02. RECURRING SCHEDULE
# GIỮ NGUYÊN - KHÔNG THUỘC PHẠM VI POMODORO
# ============================================================

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

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recurring_schedules'
    )

    title = models.CharField(max_length=150)

    day_of_week = models.IntegerField(
        choices=DAY_CHOICES
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    category = models.CharField(
        max_length=50,
        default="school"
    )

    def __str__(self):
        return (
            f"{self.title} "
            f"({self.get_day_of_week_display()})"
        )


class Course(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='courses'
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'code'],
                name='unique_course_code_per_user'
            )
        ]
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


# ============================================================
# 03. TASK
# GIỮ NGUYÊN - KHÔNG THUỘC PHẠM VI CHỈNH SỬA
# ============================================================

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

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tasks'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )

    title = models.CharField(max_length=200)

    subject_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    deadline = models.DateTimeField()

    estimated_minutes = models.IntegerField(
        help_text="Thời lượng ước tính (phút)"
    )

    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='todo'
    )

    material_url = models.URLField(
        blank=True,
        null=True
    )

    material_file = models.FileField(
        upload_to=study_material_upload_path,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt']
            ),
            validate_study_material_size,
        ],
    )

    reminder_sent_for = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.title


# ============================================================
# 04. SCHEDULE BLOCK
# GIỮ NGUYÊN - KHÔNG THUỘC PHẠM VI POMODORO
# ============================================================

class ScheduleBlock(models.Model):

    STATUS_CHOICES = [
        ('suggested', 'Được đề xuất'),
        ('confirmed', 'Đã xác nhận'),
        ('completed', 'Đã hoàn thành'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='schedule_blocks'
    )

    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blocks'
    )

    title = models.CharField(max_length=200)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    is_fixed = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='suggested'
    )

    def __str__(self):
        return (
            f"{self.title} "
            f"[{self.start_time.strftime('%d/%m %H:%M')}]"
        )


# ============================================================
# 05. POMODORO LOG - WORKSPACE 2.0
#
# MODEL DUY NHẤT ĐƯỢC NÂNG CẤP Ở C2.3
#
# HỖ TRỢ:
# - Liên kết người dùng
# - Liên kết nhiệm vụ Django
# - Lưu Quick Goal
# - Lưu phiên hoàn thành
# - Lưu phiên Gác lại
# - Lưu thời gian tập trung thực tế
# - Lưu thời gian còn lại
# - Liên kết các phiên được tiếp tục
# - Chống lưu trùng bằng session_uuid
# - Cung cấp dữ liệu Statistics / Heatmap
#
# TƯƠNG THÍCH DỮ LIỆU CŨ:
# - Giữ nguyên các trường của migration 0002
# - session_uuid cho phép NULL
# - quick_goal_title mặc định là chuỗi rỗng
# ============================================================

class PomodoroLog(models.Model):

    # --------------------------------------------------------
    # 01. TRẠNG THÁI PHIÊN
    # --------------------------------------------------------

    STATUS_CHOICES = [
        ('completed', 'Đã hoàn thành'),
        ('deferred', 'Đã gác lại'),
    ]

    # --------------------------------------------------------
    # 02. NGƯỜI DÙNG VÀ NHIỆM VỤ
    # GIỮ NGUYÊN QUAN HỆ CŨ
    # --------------------------------------------------------

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pomodoro_logs'
    )

    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # --------------------------------------------------------
    # 03. THỜI GIAN BẮT ĐẦU
    #
    # Cho phép Backend lưu thời điểm bắt đầu
    # của phiên tập trung.
    # --------------------------------------------------------

    start_time = models.DateTimeField(
        default=timezone.now
    )

    # --------------------------------------------------------
    # 04. THỜI LƯỢNG PHIÊN
    #
    # Đơn vị: phút.
    #
    # Ví dụ:
    # Người dùng thiết lập phiên 25 phút.
    # --------------------------------------------------------

    duration_minutes = models.IntegerField(
        default=25
    )

    # --------------------------------------------------------
    # 05. COMPLETED
    #
    # Giữ tương thích dữ liệu cũ.
    #
    # completed=True:
    #   Phiên hoàn thành.
    #
    # completed=False:
    #   Phiên chưa hoàn thành hoặc đã Gác lại.
    # --------------------------------------------------------

    completed = models.BooleanField(
        default=True
    )

    # --------------------------------------------------------
    # 06. STATUS
    #
    # Giá trị:
    # - completed
    # - deferred
    #
    # NULL dành cho dữ liệu từ model cũ.
    # --------------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        null=True,
        blank=True,
        db_index=True
    )

    # --------------------------------------------------------
    # 07. THỜI GIAN TẬP TRUNG THỰC TẾ
    #
    # Đơn vị: giây.
    #
    # Không bao gồm thời gian Pause.
    #
    # NULL dành cho dữ liệu cũ.
    # --------------------------------------------------------

    actual_seconds = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    # --------------------------------------------------------
    # 08. THỜI GIAN CÒN LẠI
    #
    # Đơn vị: giây.
    #
    # Khi hoàn thành:
    #   remaining_seconds = 0
    #
    # Khi Gác lại:
    #   remaining_seconds > 0
    # --------------------------------------------------------

    remaining_seconds = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    # --------------------------------------------------------
    # 09. THỜI ĐIỂM KẾT THÚC
    #
    # Backend lưu thời gian hoàn thành
    # hoặc Gác lại phiên.
    # --------------------------------------------------------

    ended_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # --------------------------------------------------------
    # 10. PHIÊN ĐƯỢC TIẾP TỤC
    #
    # Cho phép liên kết phiên mới với một
    # phiên đã Gác lại trước đó.
    #
    # Không thay đổi lịch sử phiên cũ.
    # --------------------------------------------------------

    resumed_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='continued_sessions'
    )

    # ========================================================
    # 11. SESSION UUID - C2.3
    #
    # Định danh duy nhất cho mỗi phiên tập trung.
    #
    # Ví dụ UUID:
    # 10d0c975-2d8e-425c-9a30-f380b153cb65
    #
    # UUID được Frontend tạo khi bắt đầu phiên.
    #
    # Nếu request bị gửi lại cùng UUID,
    # Backend sẽ nhận diện và không tạo log mới.
    #
    # unique=True:
    #   Database không cho phép hai bản ghi
    #   có cùng một UUID.
    #
    # null=True:
    #   Không ảnh hưởng các bản ghi cũ.
    #
    # Không dùng default=uuid.uuid4 để
    #   Backend nhận đúng UUID từ Frontend.
    # ========================================================

    session_uuid = models.UUIDField(
        null=True,
        blank=True,
        unique=True
    )

    # ========================================================
    # 12. QUICK GOAL TITLE - C2.3
    #
    # Lưu tên mục tiêu phát sinh trực tiếp
    # trong lịch sử Pomodoro.
    #
    # Ví dụ:
    # "Ôn tập thuật toán Sobel"
    #
    # Scheduled Task:
    #   task = Task thật
    #   quick_goal_title = ""
    #
    # Quick Goal:
    #   task = None
    #   quick_goal_title = "Tên mục tiêu phát sinh"
    #
    # Không tạo Task mới.
    # Không ảnh hưởng thuật toán lập lịch.
    # ========================================================

    quick_goal_title = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    # --------------------------------------------------------
    # 13. TRẠNG THÁI HIỆU LỰC
    #
    # Nếu status có giá trị:
    #   sử dụng status.
    #
    # Nếu status là NULL:
    #   đọc trường completed cũ.
    # --------------------------------------------------------

    @property
    def effective_status(self):

        if self.status is not None:
            return self.status

        if self.completed:
            return 'completed'

        return 'deferred'

    # --------------------------------------------------------
    # 14. HIỂN THỊ BẢN GHI
    # --------------------------------------------------------

    def __str__(self):

        status_labels = {
            'completed': 'Đã hoàn thành',
            'deferred': 'Đã gác lại',
        }

        status_text = status_labels.get(
            self.effective_status,
            'Không xác định'
        )

        return (
            f"{self.user.username} - "
            f"{self.duration_minutes} phút - "
            f"{status_text} "
            f"({self.start_time.strftime('%d/%m/%Y')})"
        )
