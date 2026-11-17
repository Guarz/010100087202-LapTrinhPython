from django.apps import AppConfig


class PlannerConfig(AppConfig):
    name = 'planner'

    def ready(self):
        from . import signals  # noqa: F401  (đăng ký signal lời mời lịch)
