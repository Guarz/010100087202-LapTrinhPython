try:
    from .celery import app as celery_app
except ImportError:  # Celery là tùy chọn khi chạy cục bộ
    celery_app = None

__all__ = ('celery_app',)
