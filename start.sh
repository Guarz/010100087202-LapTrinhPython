#!/usr/bin/env bash
# Khởi động trên Render (gói free chỉ có 1 web service):
# - Có REDIS_URL: chạy thêm Celery worker + beat nền trong cùng container.
#   Beat đẩy job nhắc deadline mỗi 15 phút vào Redis, worker lấy ra xử lý;
#   các job khác (lời mời lịch qua email) cũng chạy ở worker này.
# - Uvicorn phục vụ Django + FastAPI ở tiến trình chính.
set -o errexit

if [ -n "$REDIS_URL" ]; then
    celery -A core worker --beat --loglevel=info \
        --pool=solo --schedule=/tmp/celerybeat-schedule &
    echo "Celery worker + beat started (pid $!)"
fi

exec uvicorn core.asgi:application --host 0.0.0.0 --port "${PORT:-8000}" \
    --proxy-headers --forwarded-allow-ips '*'
