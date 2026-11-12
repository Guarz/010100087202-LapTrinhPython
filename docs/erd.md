# ERD – StudyPlanner

Sơ đồ quan hệ thực thể của hệ thống, khớp với `planner/models.py` sau migration `0006_userprofile_calendar_token`.

- `USER` là bảng `auth_user` có sẵn của Django (chỉ liệt kê các cột dùng tới).
- `SCHEDULE_BLOCK` đóng vai trò thực thể **Event** trong đề bài (lịch bận cố định, phiên học AI gợi ý, sự kiện nhập từ `.ics`).
- Các trường tính toán (điểm rủi ro trễ hạn, kế hoạch tuần) không lưu trong DB mà được tính từ `TASK`, `SCHEDULE_BLOCK` và `POMODORO_LOG`.

```mermaid
erDiagram
    USER ||--|| USER_PROFILE : "có hồ sơ"
    USER ||--o{ COURSE : "sở hữu"
    USER ||--o{ TASK : "tạo"
    USER ||--o{ RECURRING_SCHEDULE : "khai báo lịch bận"
    USER ||--o{ SCHEDULE_BLOCK : "sở hữu"
    USER ||--o{ POMODORO_LOG : "ghi phiên"
    COURSE |o--o{ TASK : "gồm (SET NULL)"
    TASK |o--o{ SCHEDULE_BLOCK : "được xếp lịch (SET NULL)"
    TASK |o--o{ POMODORO_LOG : "được tập trung (SET NULL)"
    POMODORO_LOG |o--o{ POMODORO_LOG : "tiếp tục từ (resumed_from)"

    USER {
        int id PK
        varchar username UK
        varchar email
        varchar password "hash"
        bool is_staff
        datetime date_joined
    }

    USER_PROFILE {
        int id PK
        int user_id FK, UK "OneToOne -> USER, CASCADE"
        varchar preferred_study_hours "mặc định 19:00-22:00"
        varchar sleep_hours "mặc định 23:00-06:00"
        uuid calendar_token UK "link đăng ký lịch .ics"
    }

    COURSE {
        int id PK
        int user_id FK "CASCADE"
        varchar code "UNIQUE (user_id, code)"
        varchar name
        text description
        datetime created_at
    }

    TASK {
        int id PK
        int user_id FK "CASCADE"
        int course_id FK "nullable, SET NULL"
        varchar title
        varchar subject_name "nullable"
        datetime deadline
        int estimated_minutes
        int priority "1 Cao, 2 TB, 3 Thấp"
        varchar status "todo, in_progress, completed"
        varchar material_url "nullable"
        varchar material_file "pdf/doc/ppt/txt, <= 10MB"
        datetime reminder_sent_for "nullable, chống gửi nhắc trùng"
        datetime created_at
    }

    RECURRING_SCHEDULE {
        int id PK
        int user_id FK "CASCADE"
        varchar title
        int day_of_week "0 Thứ Hai ... 6 Chủ Nhật"
        time start_time
        time end_time
        varchar category "mặc định school"
    }

    SCHEDULE_BLOCK {
        int id PK
        int user_id FK "CASCADE"
        int task_id FK "nullable, SET NULL"
        varchar title
        datetime start_time
        datetime end_time
        bool is_fixed "lịch cố định / nhập .ics"
        varchar status "suggested, confirmed, completed"
    }

    POMODORO_LOG {
        int id PK
        int user_id FK "CASCADE"
        int task_id FK "nullable, SET NULL"
        int resumed_from_id FK "nullable, self, SET NULL"
        uuid session_uuid UK "nullable, chống lưu trùng"
        datetime start_time
        datetime ended_at "nullable"
        int duration_minutes "mặc định 25"
        bool completed "tương thích dữ liệu cũ"
        varchar status "completed, deferred, nullable"
        int actual_seconds "nullable"
        int remaining_seconds "nullable"
        varchar quick_goal_title "mục tiêu nhanh khi task rỗng"
    }
```

## Quan hệ và ràng buộc

| Quan hệ | Lực lượng | Khi xóa cha |
|---|---|---|
| USER – USER_PROFILE | 1 – 1 | CASCADE |
| USER – COURSE / TASK / RECURRING_SCHEDULE / SCHEDULE_BLOCK / POMODORO_LOG | 1 – N | CASCADE |
| COURSE – TASK | 0..1 – N | SET NULL (task vẫn giữ) |
| TASK – SCHEDULE_BLOCK | 0..1 – N | SET NULL |
| TASK – POMODORO_LOG | 0..1 – N | SET NULL (giữ lịch sử tập trung) |
| POMODORO_LOG – POMODORO_LOG | 0..1 – N (tự tham chiếu) | SET NULL |

Ràng buộc duy nhất: `auth_user.username`, `user_profile.user_id`, `user_profile.calendar_token`, `(course.user_id, course.code)`, `pomodoro_log.session_uuid`.
