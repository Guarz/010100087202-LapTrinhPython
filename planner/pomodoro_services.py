
# ============================================================
# AI STUDYPLANNER
# planner/pomodoro_services.py
#
# C2.3.4 - POMODORO SESSION SERVICE V2
#
# CHỨC NĂNG:
# - Validate dữ liệu phiên.
# - Lưu completed / deferred.
# - Liên kết Task thuộc user hiện tại.
# - Lưu tên Quick Goal.
# - Kiểm tra session_uuid.
# - Chống ghi trùng bằng unique constraint.
#
# Không thay đổi Task, ScheduleBlock hoặc AI Assistant.
# ============================================================

from datetime import timedelta
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import PomodoroLog, Task


# ============================================================
# 01. EXCEPTION
# ============================================================

class PomodoroValidationError(ValueError):
    """Dữ liệu phiên Pomodoro không hợp lệ."""
    pass


# ============================================================
# 02. VALIDATION UTILITIES
# ============================================================

def require_integer(value, field_name):
    """
    Chỉ chấp nhận số nguyên, không nhận bool hoặc số lẻ.
    """

    if isinstance(value, bool):
        raise PomodoroValidationError(
            f"{field_name} phải là số nguyên."
        )

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        value = value.strip()

        if value.isdecimal():
            return int(value)

    raise PomodoroValidationError(
        f"{field_name} phải là số nguyên."
    )


def validate_session_uuid(data):
    """
    C2.3 - UUID bắt buộc cho phiên mới.

    UUID giúp Backend nhận diện request gửi lại.
    """

    raw_uuid = data.get("session_uuid")

    if not isinstance(raw_uuid, str):
        raise PomodoroValidationError(
            "Thiếu session_uuid hoặc UUID không hợp lệ."
        )

    raw_uuid = raw_uuid.strip()

    try:
        session_uuid = UUID(raw_uuid)
    except (ValueError, AttributeError):
        raise PomodoroValidationError(
            "session_uuid không đúng định dạng UUID."
        )

    return session_uuid


def validate_status(data):
    """
    Trạng thái chỉ có completed hoặc deferred.
    """

    status = data.get("status")

    if status not in ("completed", "deferred"):
        raise PomodoroValidationError(
            "Trạng thái phiên không hợp lệ. "
            "Chỉ chấp nhận 'completed' hoặc 'deferred'."
        )

    return status


def validate_duration(data):
    """
    Thời lượng phiên từ 1 đến 180 phút.
    """

    duration = require_integer(
        data.get("duration_minutes"),
        "duration_minutes"
    )

    if not 1 <= duration <= 180:
        raise PomodoroValidationError(
            "Thời lượng phiên phải từ 1 đến 180 phút."
        )

    return duration


def validate_seconds(
    data,
    status,
    duration_minutes
):
    """
    Kiểm tra số giây tập trung và thời gian còn lại.

    completed:
        remaining_seconds = 0

    deferred:
        remaining_seconds > 0
    """

    maximum_seconds = duration_minutes * 60

    raw_actual = data.get("actual_seconds")

    # Tương thích logic cũ đối với completed.
    if raw_actual is None and status == "completed":
        actual_seconds = maximum_seconds

    elif raw_actual is None:
        raise PomodoroValidationError(
            "Phiên Gác lại cần actual_seconds."
        )

    else:
        actual_seconds = require_integer(
            raw_actual,
            "actual_seconds"
        )

    raw_remaining = data.get("remaining_seconds")

    if status == "completed":

        if raw_remaining is None:
            remaining_seconds = 0

        else:
            remaining_seconds = require_integer(
                raw_remaining,
                "remaining_seconds"
            )

        if remaining_seconds != 0:
            raise PomodoroValidationError(
                "Phiên hoàn thành phải có "
                "remaining_seconds = 0."
            )

        if not 1 <= actual_seconds <= maximum_seconds:
            raise PomodoroValidationError(
                "actual_seconds của phiên hoàn thành "
                "phải lớn hơn 0 và không vượt thời lượng."
            )

    else:

        if raw_remaining is None:
            raise PomodoroValidationError(
                "Phiên Gác lại cần remaining_seconds."
            )

        remaining_seconds = require_integer(
            raw_remaining,
            "remaining_seconds"
        )

        if not 0 <= actual_seconds <= maximum_seconds:
            raise PomodoroValidationError(
                "actual_seconds không hợp lệ."
            )

        if not 1 <= remaining_seconds <= maximum_seconds:
            raise PomodoroValidationError(
                "remaining_seconds của phiên Gác lại "
                "phải lớn hơn 0."
            )

        # Sai số làm tròn tối đa 1 giây.
        if (
            actual_seconds + remaining_seconds
            > maximum_seconds + 1
        ):
            raise PomodoroValidationError(
                "Tổng thời gian tập trung và còn lại "
                "vượt thời lượng phiên."
            )

    return actual_seconds, remaining_seconds


# ============================================================
# 03. VALIDATE TASK
# ============================================================

def resolve_task(user, data):
    """
    Chỉ liên kết Task thuộc user đã đăng nhập.
    """

    task_id = data.get("task_id")

    if task_id is None or task_id == "":
        return None

    task_id = require_integer(
        task_id,
        "task_id"
    )

    if task_id <= 0:
        raise PomodoroValidationError(
            "task_id không hợp lệ."
        )

    task = Task.objects.filter(
        id=task_id,
        user=user
    ).first()

    if task is None:
        raise PomodoroValidationError(
            "Không tìm thấy nhiệm vụ "
            "thuộc tài khoản hiện tại."
        )

    return task


# ============================================================
# 04. VALIDATE QUICK GOAL
# ============================================================

def validate_quick_goal(data, task):
    """
    Quick Goal chỉ lưu tên trong PomodoroLog.

    Không tạo Task mới.
    Không cho một phiên vừa có Task vừa có Quick Goal.
    """

    raw_title = data.get(
        "quick_goal_title",
        ""
    )

    if raw_title is None:
        raw_title = ""

    if not isinstance(raw_title, str):
        raise PomodoroValidationError(
            "quick_goal_title phải là chuỗi."
        )

    title = raw_title.strip()

    if len(title) > 200:
        raise PomodoroValidationError(
            "Tên Quick Goal không được vượt quá 200 ký tự."
        )

    if task is not None and title:
        raise PomodoroValidationError(
            "Một phiên không thể đồng thời liên kết "
            "Scheduled Task và Quick Goal."
        )

    return title


# ============================================================
# 05. VALIDATE RESUMED SESSION
# ============================================================

def resolve_resumed_from(user, data):
    """
    Chỉ tiếp tục từ phiên Gác lại của cùng người dùng.
    """

    resumed_from_id = data.get(
        "resumed_from_id"
    )

    if resumed_from_id is None or resumed_from_id == "":
        return None

    resumed_from_id = require_integer(
        resumed_from_id,
        "resumed_from_id"
    )

    if resumed_from_id <= 0:
        raise PomodoroValidationError(
            "resumed_from_id không hợp lệ."
        )

    previous_log = PomodoroLog.objects.filter(
        id=resumed_from_id,
        user=user
    ).first()

    if previous_log is None:
        raise PomodoroValidationError(
            "Không tìm thấy phiên trước đó."
        )

    if previous_log.effective_status != "deferred":
        raise PomodoroValidationError(
            "Chỉ có thể tiếp tục từ một phiên đã Gác lại."
        )

    return previous_log


# ============================================================
# 06. VALIDATE START TIME
# ============================================================

def resolve_start_time(
    data,
    actual_seconds,
    ended_at
):
    """
    Client gửi started_at ISO 8601 có timezone.

    Nếu không gửi, ước lượng theo actual_seconds.
    """

    raw_started_at = data.get("started_at")

    if not raw_started_at:
        return ended_at - timedelta(
            seconds=actual_seconds
        )

    if not isinstance(raw_started_at, str):
        raise PomodoroValidationError(
            "started_at phải là chuỗi ISO 8601."
        )

    started_at = parse_datetime(
        raw_started_at
    )

    if started_at is None:
        raise PomodoroValidationError(
            "started_at không đúng định dạng ISO 8601."
        )

    if timezone.is_naive(started_at):
        raise PomodoroValidationError(
            "started_at phải kèm thông tin múi giờ."
        )

    if started_at > ended_at + timedelta(minutes=5):
        raise PomodoroValidationError(
            "started_at không được nằm trong tương lai."
        )

    if started_at < ended_at - timedelta(hours=24):
        raise PomodoroValidationError(
            "Thời điểm bắt đầu quá xa thời điểm kết thúc."
        )

    return started_at


# ============================================================
# 07. KIỂM TRA REQUEST TRÙNG
# ============================================================

def ensure_duplicate_matches(
    existing_log,
    user,
    task,
    quick_goal_title,
    status,
    duration_minutes,
    actual_seconds,
    remaining_seconds,
    started_at,
    resumed_from
):
    """
    UUID đã tồn tại phải thuộc đúng người dùng và
    có cùng nội dung phiên.

    Nếu khác dữ liệu thì từ chối.
    """

    if existing_log.user_id != user.id:
        raise PomodoroValidationError(
            "session_uuid đã được sử dụng."
        )

    expected_task_id = (
        task.id
        if task is not None
        else None
    )

    expected_resumed_id = (
        resumed_from.id
        if resumed_from is not None
        else None
    )

    same_content = all([
        existing_log.task_id == expected_task_id,

        existing_log.quick_goal_title == quick_goal_title,

        existing_log.status == status,

        existing_log.duration_minutes == duration_minutes,

        existing_log.actual_seconds == actual_seconds,

        existing_log.remaining_seconds == remaining_seconds,

        existing_log.start_time == started_at,

        existing_log.resumed_from_id == expected_resumed_id,
    ])

    if not same_content:
        raise PomodoroValidationError(
            "session_uuid đã tồn tại với dữ liệu khác. "
            "Không thể ghi đè phiên đã lưu."
        )

    return existing_log


# ============================================================
# 08. SAVE SESSION
# ============================================================

def save_pomodoro_session(user, data):
    """
    Điểm vào chính để lưu một phiên Pomodoro.

    Lần đầu:
        Tạo PomodoroLog mới.

    Lần sau cùng session_uuid và cùng dữ liệu:
        Trả lại bản ghi đã có.

    Cùng UUID nhưng dữ liệu khác:
        Từ chối.

    Database unique constraint là lớp bảo vệ cuối cùng.
    """

    if not user or not user.is_authenticated:
        raise PomodoroValidationError(
            "Vui lòng đăng nhập để lưu phiên tập trung."
        )

    if not isinstance(data, dict):
        raise PomodoroValidationError(
            "Dữ liệu phiên phải là JSON object."
        )

    # --------------------------------------------------------
    # 01. VALIDATE REQUEST
    # --------------------------------------------------------

    session_uuid = validate_session_uuid(data)

    status = validate_status(data)

    duration_minutes = validate_duration(data)

    actual_seconds, remaining_seconds = validate_seconds(
        data,
        status,
        duration_minutes
    )

    task = resolve_task(user, data)

    quick_goal_title = validate_quick_goal(
        data,
        task
    )

    resumed_from = resolve_resumed_from(
        user,
        data
    )

    # --------------------------------------------------------
    # 02. KIỂM TRA UUID ĐÃ TỒN TẠI
    # --------------------------------------------------------

    existing_log = PomodoroLog.objects.filter(
        session_uuid=session_uuid
    ).first()

    if existing_log is not None:

        return ensure_duplicate_matches(
            existing_log=existing_log,
            user=user,
            task=task,
            quick_goal_title=quick_goal_title,
            status=status,
            duration_minutes=duration_minutes,
            actual_seconds=actual_seconds,
            remaining_seconds=remaining_seconds,
            started_at=resolve_start_time(
                data,
                actual_seconds,
                timezone.now()
            ),
            resumed_from=resumed_from
        )

    # --------------------------------------------------------
    # 03. XÁC ĐỊNH THỜI GIAN
    # --------------------------------------------------------

    ended_at = timezone.now()

    started_at = resolve_start_time(
        data,
        actual_seconds,
        ended_at
    )

    completed = status == "completed"

    # --------------------------------------------------------
    # 04. TẠO LOG
    #
    # transaction.atomic:
    # Nếu hai request tạo cùng UUID đồng thời,
    # ràng buộc unique chỉ cho phép một bản ghi.
    # --------------------------------------------------------

    try:

        with transaction.atomic():

            log = PomodoroLog.objects.create(
                user=user,
                task=task,
                start_time=started_at,
                duration_minutes=duration_minutes,
                completed=completed,
                status=status,
                actual_seconds=actual_seconds,
                remaining_seconds=remaining_seconds,
                ended_at=ended_at,
                resumed_from=resumed_from,
                session_uuid=session_uuid,
                quick_goal_title=quick_goal_title
            )

        return log

    except IntegrityError:

        # Một request khác có thể vừa ghi cùng UUID.
        # Đọc lại bản ghi và kiểm tra nội dung.
        existing_log = PomodoroLog.objects.filter(
            session_uuid=session_uuid
        ).first()

        if existing_log is None:
            # Không che giấu lỗi database không liên quan.
            raise

        return ensure_duplicate_matches(
            existing_log=existing_log,
            user=user,
            task=task,
            quick_goal_title=quick_goal_title,
            status=status,
            duration_minutes=duration_minutes,
            actual_seconds=actual_seconds,
            remaining_seconds=remaining_seconds,
            started_at=started_at,
            resumed_from=resumed_from
        )
