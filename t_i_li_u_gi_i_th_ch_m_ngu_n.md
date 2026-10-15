# TÀI LIỆU GIẢI THÍCH CHI TIẾT MÃ NGUỒN VÀ KIẾN TRÚC HỆ THỐNG
**Dự án:** Ứng dụng Lập Kế Hoạch Học Tập Thông Minh Có Cố Vấn AI (AI Study Planner)  
**Công nghệ chủ đạo:** Django 5, PostgreSQL (Supabase Pooler), FullCalendar v6, Tailwind CSS, FontAwesome v6, OpenAI API, WhiteNoise, Render

---

## MỤC LỤC
1. [Tổng Quan Kiến Trúc Hệ Thống](#1-tổng-quan-kiến-trúc-hệ-thống)
2. [Cấu Trúc Thư Mục Dự Án](#2-cấu-trúc-thư-mục-dự-án)
3. [Chi Tiết Tầng Cấu Hình & Hạ Tầng (Core)](#3-chi-tiết-tầng-cấu-hình--hạ-tầng-core)
4. [Tầng Cơ Sở Dữ Liệu & Mô Hình Dữ Liệu (Models)](#4-tầng-cơ-sở-dữ-liệu--mô-hình-dữ-liệu-models)
5. [Thuật Toán Xếp Lịch Tuần Tự Động (Heuristic Scheduler)](#5-thuật-toán-xếp-lịch-tuần-tự-động-heuristic-scheduler)
6. [Module Cố Vấn Trí Tuệ Nhân Tạo & Đánh Giá Rủi Ro (AI Assistant)](#6-module-cố-vấn-trí-tuệ-nhân-tạo--đánh-giá-rủi-ro-ai-assistant)
7. [Tầng Điều Khiển & Giao Tiếp API (Views & URLs)](#7-tầng-điều-khiển--giao-tiếp-api-views--urls)
8. [Tầng Giao Diện & Trải Nghiệm Người Dùng (Templates)](#8-tầng-giao-diện--trải-nghiệm-người-dùng-templates)
9. [Luồng Vận Hành Toàn Trình (End-to-End Workflow)](#9-luồng-vận-hành-toàn-trình-end-to-end-workflow)
10. [Hướng Dẫn Triển Khai & Vận Hành Trực Tuyến (Deployment)](#10-hướng-dẫn-triển-khai--vận-hành-trực-tuyến-deployment)

---

## 1. Tổng Quan Kiến Trúc Hệ Thống

Hệ thống được xây dựng theo mô hình **Monolithic hiện đại**, kết hợp sức mạnh xử lý nghiệp vụ của Django với giao diện tương tác động phía client thông qua Web APIs:

*   **Tầng Trình Diễn (Frontend):** Sử dụng kiến trúc Server-Side Rendering (Django Templates) tích hợp **Tailwind CSS** (qua CDN) cho giao diện chuẩn responsive, bộ icon vector đồng bộ từ **FontAwesome v6**, cùng thư viện **FullCalendar v6** hỗ trợ tương tác kéo-thả (Drag & Drop) và Web Audio API tạo âm báo cho bộ đếm Pomodoro.
*   **Tầng Xử Lý Trung Tâm (Backend):** Sử dụng **Django 5** đóng vai trò điều phối luồng dữ liệu, xử lý xác thực (Authentication), bảo vệ không gian dữ liệu riêng biệt cho từng người dùng (`@login_required`), và thực thi thuật toán xếp lịch Heuristic.
*   **Tầng Dữ Liệu (Database):** Cơ sở dữ liệu quan hệ PostgreSQL được lưu trữ trên nền tảng đám mây **Supabase**, kết nối qua giao thức IPv4 **Session Pooler** đảm bảo tính ổn định cao và chống nghẽn kết nối mạng.
*   **Tầng Dịch Vụ Mở Rộng (External Services):** Tích hợp **OpenAI API (`gpt-4o-mini`)** với chế độ xuất định dạng JSON có cấu trúc (`response_format={"type": "json_object"}`) cùng cơ chế dự phòng Heuristic nội bộ phòng ngừa lỗi gián đoạn mạng.

---

## 2. Cấu Trúc Thư Mục Dự Án

```text
study_planner_django/
├── core/                           # Cấu hình mức hệ thống của Django
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py                 # File cấu hình trung tâm (Database, Static, Auth)
│   ├── urls.py                     # Điều hướng URL cấp cao nhất
│   └── wsgi.py                     # Entry point cho Web Server (Gunicorn)
├── planner/                        # Ứng dụng nghiệp vụ chính
│   ├── __init__.py
│   ├── admin.py                    # Đăng ký các bảng vào giao diện Django Admin
│   ├── ai_assistant.py             # Module tính toán rủi ro và tích hợp OpenAI
│   ├── apps.py
│   ├── forms.py                    # Form nhập Task, Lịch bận và Đăng ký người dùng
│   ├── models.py                   # Khai báo cấu trúc 5 bảng CSDL (ORM)
│   ├── scheduler.py                # Thuật toán Heuristic xếp lịch tự động
│   ├── urls.py                     # Định tuyến các trang và API nội bộ
│   └── views.py                    # Controller xử lý logic nghiệp vụ và dữ liệu
├── templates/                      # Thư mục giao diện dùng chung
│   ├── base.html                   # Khung chuẩn: Navbar mobile overlay, Tailwind, FontAwesome
│   └── planner/
│       ├── ai_assistant.html       # Dashboard phân tích thói quen và cảnh báo deadline
│       ├── calendar.html           # Giao diện Lịch biểu tương tác FullCalendar v6
│       ├── login.html              # Màn hình đăng nhập tài khoản
│       ├── pomodoro.html           # Bộ đếm Pomodoro, âm báo Web Audio & thống kê
│       ├── recurring_list.html     # Quản lý thời khóa biểu / ca bận cố định
│       ├── register.html           # Màn hình đăng ký tài khoản sinh viên
│       └── task_list.html          # Danh sách nhiệm vụ, hạn nộp và tài liệu ôn tập
├── build.sh                        # Script tự động hóa cho môi trường Render
├── manage.py                       # CLI điều khiển dự án
└── requirements.txt                # Danh sách thư viện Python phụ thuộc
```

---

## 3. Chi Tiết Tầng Cấu Hình & Hạ Tầng (Core)

File `core/settings.py` chịu trách nhiệm thiết lập môi trường vận hành an toàn và tương thích giữa máy tính cá nhân (Local) và máy chủ đám mây (Production).

### 3.1. Quản lý Biến Môi Trường Bảo Mật
```python
import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Đọc Secret Key và trạng thái Debug từ môi trường
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['*']
```
*   **Bảo mật:** `SECRET_KEY` được nạp từ biến môi trường của hệ điều hành hoặc máy chủ đám mây để tránh lộ khóa ký phiên người dùng lên GitHub.
*   **Chế độ Production:** Biến `DEBUG` mặc định tắt (`False`) trên máy chủ online để ngăn chặn việc hiển thị khung gỡ lỗi (traceback) chứa thông tin nội bộ của server khi gặp ngoại lệ.

### 3.2. Cấu hình Kết Nối Cơ Sở Dữ Liệu Đám Mây
```python
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', 'postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres'),
        conn_max_age=600,
        ssl_require=True
    )
}
```
*   **`dj_database_url`:** Tự động phân giải chuỗi kết nối chuẩn URI (`postgresql://user:pass@host:port/dbname`) thành từ điển tham số của Django.
*   **`conn_max_age=600`:** Bật chế độ tái sử dụng kết nối (Connection Pooling) trong 10 phút, giúp giảm thiểu độ trễ kết nối TCP và chi phí thiết lập kết nối SSL mỗi lần người dùng bấm chuyển trang.

### 3.3. Phục vụ Tệp Tĩnh (Static Files) với WhiteNoise
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Nằm ngay sau SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ...
]

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```
*   **Giải quyết lỗi mất CSS Admin khi `DEBUG=False`:** Khi tắt Debug, Django mặc định từ chối nạp file tĩnh. **WhiteNoise** can thiệp trực tiếp vào middleware để tự động nạp, nén dữ liệu (gzip/brotli) và đính kèm mã băm định danh (fingerprinting hash) vào tên file nhằm triệt tiêu lỗi lưu cache cũ trên trình duyệt.

---

## 4. Tầng Cơ Sở Dữ Liệu & Mô Hình Dữ Liệu (Models)

Được định nghĩa trong `planner/models.py`, gồm 5 bảng dữ liệu liên kết chặt chẽ:

```mermaid
erDiagram
    User ||--|| UserProfile : "mở rộng thông tin"
    User ||--o{ RecurringSchedule : "sở hữu lịch lặp"
    User ||--o{ Task : "tạo nhiệm vụ"
    User ||--o{ ScheduleBlock : "quản lý khối lịch"
    User ||--o{ PomodoroLog : "ghi nhật ký tập trung"
    Task ||--o{ ScheduleBlock : "phân rã thành"
    Task ||--o{ PomodoroLog : "gắn phiên học với"
```

### 4.1. Bảng `UserProfile` (Thông số cấu hình cá nhân)
*   **`user`:** Khóa ngoại quan hệ 1-1 với model chuẩn `django.contrib.auth.models.User`.
*   **`preferred_study_hours`:** Khung giờ sinh viên tỉnh táo và tập trung nhất (VD: `"19:00-22:00"`). Thuật toán sẽ ưu tiên lấp các task khó vào khung giờ này.
*   **`sleep_hours`:** Giờ ngủ cố định (VD: `"23:00-06:00"`). Đóng vai trò là **Ràng buộc cứng (Hard Constraint)**; thuật toán tuyệt đối không được phép xếp bất kỳ slot học nào vào khoảng thời gian này.

### 4.2. Bảng `RecurringSchedule` (Thời khóa biểu cố định hàng tuần)
*   **`day_of_week`:** Số nguyên đại diện cho thứ trong tuần (`0`: Thứ Hai, ..., `6`: Chủ Nhật).
*   **`start_time`, `end_time`:** Thời gian bắt đầu và kết thúc cố định trong ngày (`TimeField`).
*   **`category`:** Phân loại lịch (`school`: học trên trường, `part_time`: đi làm thêm, `personal`: việc cá nhân).
*   *Mục đích:* Người dùng chỉ nhập 1 lần duy nhất cho toàn học kỳ. Thuật toán tự động nhân bản thành các khung bận thực tế trên lịch.

### 4.3. Bảng `Task` (Nhiệm vụ, Bài tập & Hạn chót)
*   **`title`:** Tên bài tập / nhiệm vụ cần làm.
*   **`deadline`:** Mốc thời gian hạn chót (`DateTimeField`).
*   **`estimated_minutes`:** Tổng thời lượng sinh viên ước tính để hoàn thành (phút).
*   **`priority`:** Mức độ ưu tiên (`1`: Cao, `2`: Trung bình, `3`: Thấp).
*   **`material_url`:** Liên kết lưu trữ tài liệu tham khảo (Google Drive, Slide, Notion).
*   **`status`:** Trạng thái (`todo`, `in_progress`, `completed`).

### 4.4. Bảng `ScheduleBlock` (Khối lịch tuần hiển thị trên Calendar)
*   **`start_time`, `end_time`:** Mốc thời gian tuyệt đối gồm cả ngày và giờ (`DateTimeField`).
*   **`is_fixed`:** Cờ nhị phân phân loại:
    *   `True`: Lịch bận cố định sinh ra từ `RecurringSchedule` (ngăn cản kéo thả).
    *   `False`: Phiên tự học do thuật toán gợi ý (cho phép kéo thả dời giờ).
*   **`status`:** Trạng thái khối lịch (`suggested`: AI vừa sinh, `confirmed`: người dùng đã xác nhận hoặc chỉnh sửa giờ, `completed`: đã hoàn thành).

### 4.5. Bảng `PomodoroLog` (Nhật ký thực thi phiên học)
*   **`task`:** Khóa ngoại liên kết tới `Task` đang làm trong phiên học (có thể để `null` nếu sinh viên tự học tự do).
*   **`duration_minutes`:** Số phút tập trung thực tế (mặc định 25 phút).
*   **`completed`:** Xác nhận sinh viên học đủ trọn vẹn phiên hay bị dừng giữa chừng.

---

## 5. Thuật Toán Xếp Lịch Tuần Tự Động (Heuristic Scheduler)

Tọa lạc tại `planner/scheduler.py`, hàm `auto_generate_weekly_schedule(user)` giải quyết bài toán phân bổ khoảng trống (Interval Scheduling) theo 6 giai đoạn:

```
[Bắt đầu lập lịch]
   │
   ├── Giai đoạn 1: Đọc UserProfile (sleep_hours) -> Xác định khung giờ thức - ngủ
   │
   ├── Giai đoạn 2: Nhân bản RecurringSchedule của tuần -> Lưu thành ScheduleBlock (is_fixed=True)
   │
   ├── Giai đoạn 3: Thu thập toàn bộ khối bận -> Quét và trích xuất các Free Slots (>= 45 phút)
   │
   ├── Giai đoạn 4: Lấy danh sách Task chưa xong -> Sắp xếp: Ưu tiên Cao trước, Deadline gần trước
   │
   └── Giai đoạn 5: Heuristic Placement:
             ├── Cắt nhỏ Task thành các block tối đa 90 phút (tránh kiệt sức)
             ├── Đặt block vào Free Slot trước hạn deadline
             └── Trừ thời lượng của Task, thêm 10 phút nghỉ giữa 2 block
```

### Các nguyên tắc kỹ thuật cốt lõi:
1.  **Bảo vệ dữ liệu người dùng đã chỉnh:**
    Lệnh xóa chỉ tác động lên các khối chưa được người dùng duyệt:
    ```python
    ScheduleBlock.objects.filter(
        user=user, 
        is_fixed=False, 
        status='suggested', 
        start_time__gte=now
    ).delete()
    ```
    Các khối có `status='confirmed'` (do người dùng tự kéo thả tay trước đó) được giữ nguyên vẹn.
2.  **Chia nhỏ phiên học (Session Splitting):**
    Nếu bài tập cần 180 phút, thuật toán không xếp liền 3 tiếng một lúc mà tách thành các block tối đa 90 phút:
    ```python
    session_duration = min(remaining_time, current_slot['minutes'], 90)
    ```
3.  **Tạo khoảng đệm nghỉ ngơi (Buffer Time):**
    Sau mỗi khối học được tạo, thuật toán tự cộng thêm 10 phút nghỉ trước khi xét tiếp phiên sau:
    ```python
    current_slot['start'] = session_end + timedelta(minutes=10)
    ```

---

## 6. Module Cố Vấn Trí Tuệ Nhân Tạo & Đánh Giá Rủi Ro (AI Assistant)

File `planner/ai_assistant.py` đảm nhận việc tổng hợp thông tin và kết nối với Large Language Model.

### 6.1. Thuật Toán Đo Lường Rủi Ro Nội Bộ
Trước khi gọi AI, hệ thống tính toán toán học để xác định các bài tập có nguy cơ trễ hạn cao:
*   Tính thời gian còn lại:
    $$\text{hours\_left} = \frac{(\text{deadline} - \text{now}).\text{total\_seconds}())}{3600}$$
*   Quy tắc báo động: Một nhiệm vụ bị xem là có rủi ro trễ hạn nếu:
    $$0 < \text{hours\_left} \times 60 < 1.5 \times \text{estimated\_minutes}$$
    *(Nghĩa là quỹ thời gian thực tế còn lại quá sát so với khối lượng công việc cần làm).*

### 6.2. Cơ Chế Dự Phòng Không Gián Đoạn (Fault-Tolerant Fallback)
Nếu người dùng chưa cấu hình `OPENAI_API_KEY` hoặc máy chủ OpenAI gặp sự cố:
```python
if not api_key:
    return {
        "daily_summary": f"Hôm nay bạn có {len(tasks_data)} nhiệm vụ đang chờ xử lý...",
        "risk_warnings": [...],
        "habit_advice": f"Trong 7 ngày qua, bạn đã hoàn thành {pomo_count} phiên Pomodoro...",
        "is_ai_generated": False
    }
```
*   Hệ thống tự động trả về số liệu tính toán nội bộ, đảm bảo website **không bao giờ bị lỗi 500 (Zero-crash)** khi thiếu API Key.

### 6.3. Tích Hợp OpenAI API với Structured JSON
Khi có API Key hợp lệ, hệ thống gửi toàn bộ danh sách deadline kèm lịch sử Pomodoro và ép API phản hồi đúng chuẩn JSON:
```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Bạn là chuyên gia cố vấn lập kế hoạch học tập. Trả về định dạng JSON thuần."},
        {"role": "user", "content": prompt}
    ],
    response_format={"type": "json_object"},
    temperature=0.7
)
```

---

## 7. Tầng Điều Khiển & Giao Tiếp API (Views & URLs)

File `planner/views.py` và `planner/urls.py` quản lý toàn bộ luồng giao tiếp giữa client và máy chủ:

| Đường dẫn (URL Pattern) | View Function | Phương thức | Mô tả chức năng & Bảo mật |
| :--- | :--- | :--- | :--- |
| `/` | `task_list` | GET, POST | Trang chủ: Quản lý danh sách Task, Form tạo mới (`@login_required`). |
| `/task/<id>/toggle/` | `toggle_task_status` | GET | Chuyển đổi trạng thái giữa `todo` và `completed`. |
| `/task/<id>/delete/` | `delete_task` | GET | Xóa hoàn toàn một bài tập khỏi cơ sở dữ liệu. |
| `/recurring/` | `recurring_schedule_list` | GET, POST | Quản lý thời khóa biểu và ca làm thêm lặp lại hàng tuần. |
| `/recurring/<id>/delete/`| `delete_recurring` | GET | Xóa một khung giờ bận cố định. |
| `/calendar/` | `calendar_view` | GET | Render trang giao diện Lịch tuần FullCalendar v6. |
| `/api/calendar-events/` | `calendar_events_api` | GET | API trả về JSON chứa toàn bộ Task và ScheduleBlock của user. |
| `/api/update-block-time/`| `update_block_time_api` | POST | API nhận dữ liệu khi người dùng kéo-thả sự kiện trên lịch. |
| `/auto-schedule/` | `trigger_auto_schedule` | GET | Kích hoạt thuật toán Heuristic lập lịch 7 ngày tới. |
| `/pomodoro/` | `pomodoro_view` | GET | Đồng hồ đếm ngược Pomodoro và nhật ký năng suất. |
| `/api/save-pomodoro/` | `save_pomodoro_api` | POST | API ghi nhận một phiên học tập 25 phút đã hoàn thành. |
| `/ai-assistant/` | `ai_assistant_view` | GET | Trang phân tích thói quen và cảnh báo nguy cơ trễ hạn. |
| `/register/` | `register_view` | GET, POST | Đăng ký tài khoản mới và tự động khởi tạo UserProfile. |
| `/login/` | `login_view` | GET, POST | Xác thực phiên người dùng (`django.contrib.auth`). |
| `/logout/` | `logout_view` | GET | Hủy phiên đăng nhập và đưa về màn hình Login. |

---

## 8. Tầng Giao Diện & Trải Nghiệm Người Dùng (Templates)

Toàn bộ giao diện được xây dựng nhất quán thông qua hệ thống template kế thừa của Django:

### 8.1. `templates/base.html`
*   **Floating Backdrop Mobile Menu:** Thanh menu di động sử dụng lớp định vị `absolute top-16 left-0 w-full z-50` kết hợp lớp phủ nền `fixed inset-0 top-16 bg-gray-900/60 backdrop-blur-sm z-40`. Khi bấm mở, menu nổi đè lên nội dung và vô hiệu hóa mọi thao tác bấm/cuộn chuột phía sau mà không làm xô lệch cấu trúc trang.
*   **Chống hiện tượng Scrollbar Layout Shift:** Thẻ `<html>` được gán thuộc tính `class="[scrollbar-gutter:stable]"` giúp trình duyệt luôn bảo lưu sẵn không gian của thanh cuộn dọc trên mọi trang, triệt tiêu hiện tượng lệch 8px khi chuyển giữa các trang ngắn và dài.

### 8.2. `templates/planner/calendar.html`
*   **Đồng bộ icon FontAwesome vào FullCalendar:** Thay vì dùng emoji, hệ thống can thiệp vào quá trình render của FullCalendar qua hook `eventContent`:
    ```javascript
    eventContent: function(arg) {
        const iconClass = arg.event.extendedProps.icon || 'fa-solid fa-calendar';
        const container = document.createElement('div');
        container.className = 'flex items-center gap-1.5 p-0.5 truncate text-white leading-tight';
        container.innerHTML = `<i class="${iconClass} text-[11px] opacity-90"></i> <span class="truncate font-medium text-xs">${arg.event.title}</span>`;
        return { domNodes: [container] };
    }
    ```
*   **Xử lý kéo-thả (Drag & Drop):** Bắt sự kiện `eventDrop` và gửi request AJAX tới `/api/update-block-time/`, lưu thời gian mới vào database ngay lập tức.

### 8.3. `templates/planner/pomodoro.html`
*   **Web Audio API (Âm thanh độc lập):** Sử dụng `AudioContext` và `OscillatorNode` phát âm thanh sóng sin tần số $880\text{ Hz}$ (nốt La - A5) trong $0.8$ giây khi hết giờ, không cần lưu trữ hoặc tải các file `.mp3` từ bên ngoài.
*   **Liên kết tài liệu ôn tập:** Tự động bắt sự kiện thay đổi của thẻ `<select>` chọn môn học; nếu môn có trường `material_url`, giao diện tự động bật nút truy cập nhanh tài liệu.

---

## 9. Luồng Vận Hành Toàn Trình (End-to-End Workflow)

```mermaid
sequenceDiagram
    autonumber
    actor User as Sinh Viên
    participant UI as Giao Diện Web
    participant Server as Django Backend
    participant DB as PostgreSQL (Supabase)
    participant AI as OpenAI API

    User->>UI: 1. Đăng ký tài khoản (Username, Password)
    UI->>Server: Gửi POST /register/
    Server->>DB: Lưu User và khởi tạo UserProfile
    Server-->>UI: Xác thực phiên và chuyển hướng đến trang chủ

    User->>UI: 2. Nhập ca học thứ Ba (07:30 - 11:30)
    UI->>Server: Gửi POST /recurring/
    Server->>DB: Lưu vào bảng RecurringSchedule

    User->>UI: 3. Thêm bài tập "Đồ án Python", Deadline Thứ Sáu, ước tính 180 phút
    UI->>Server: Gửi POST /
    Server->>DB: Lưu vào bảng Task (priority=1, status='todo')

    User->>UI: 4. Mở trang Calendar, bấm "Tự động lập lịch tuần"
    UI->>Server: Gửi GET /auto-schedule/
    Server->>DB: Truy vấn RecurringSchedule & UserProfile
    Note over Server: Tính toán các khoảng trống (Free Slots).<br/>Tách bài tập 180 phút thành 2 block 90 phút.
    Server->>DB: Ghi các ScheduleBlock vào database
    Server-->>UI: FullCalendar tự render các ô màu xanh lên lịch

    User->>UI: 5. Chuyển sang Pomodoro, chọn bài "Đồ án Python" và bấm Bắt đầu
    Note over UI: Đồng hồ đếm ngược 25 phút.<br/>Hết giờ phát chuông nốt La (880Hz).
    UI->>Server: Gửi POST /api/save-pomodoro/ (25 phút)
    Server->>DB: Ghi bản ghi hoàn thành vào PomodoroLog

    User->>UI: 6. Mở trang "Trợ lý AI"
    UI->>Server: Gửi GET /ai-assistant/
    Server->>DB: Đọc lịch sử Pomodoro & tính rủi ro trễ hạn đồ án
    Server->>AI: Gửi context phân tích qua Chat Completion
    AI-->>Server: Trả về JSON chứa tóm tắt, cảnh báo và lời khuyên
    Server-->>UI: Hiển thị báo cáo trực quan kèm thẻ cảnh báo khẩn cấp
```

---

## 10. Hướng Dẫn Triển Khai & Vận Hành Trực Tuyến (Deployment)

Hệ thống được thiết kế tối ưu hóa cho nền tảng PaaS **Render** kết hợp **Supabase**:

### 10.1. File Thực Thi Build Tự Động (`build.sh`)
```bash
#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
```
*   `set -o errexit`: Lệnh này đảm bảo nếu có bất kỳ bước nào bị lỗi (như thiếu package), toàn bộ quá trình build sẽ dừng lập tức để tránh triển khai mã nguồn lỗi lên môi trường thực tế.
*   `collectstatic --no-input`: Gom toàn bộ static file (bao gồm cả static của Django Admin) về thư mục `staticfiles/` để WhiteNoise phục vụ.
*   `migrate`: Tự động đồng bộ các bảng cơ sở dữ liệu lên Supabase mỗi khi có commit mới trên nhánh `main`.

### 10.2. Cấu Hình Biến Môi Trường Trên Render (Environment Variables)

| Key | Value (Mẫu) | Ghi Chú |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:5432/postgres` | Chuỗi kết nối **Session Pooler** của Supabase (hỗ trợ IPv4). |
| `SECRET_KEY` | `django-insecure-prod-9a8f7c6e5d4b3a210fedcba987654321` | Chuỗi ký tự ngẫu nhiên dùng để mã hóa session người dùng. |
| `DEBUG` | `False` | Tắt chế độ gỡ lỗi trên môi trường Production. |
| `PYTHON_VERSION` | `3.12.3` | Khai báo môi trường runtime Python ổn định. |
| `OPENAI_API_KEY` | `sk-proj-...` | Khóa API OpenAI (tùy chọn; nếu không có, hệ thống tự kích hoạt chế độ Heuristic dự phòng). |

### 10.3. Lệnh Khởi Chạy Web Server (Start Command)
```text
gunicorn core.wsgi:application
```
Tiến trình **Gunicorn** khởi chạy ứng dụng WSGI của Django với khả năng xử lý đồng thời nhiều worker, sẵn sàng phục vụ hàng ngàn yêu cầu truy cập trực tuyến với độ trễ thấp.