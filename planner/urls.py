# planner/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.task_list, name='task_list'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('calendar/', views.calendar_view, name='calendar_view'),
    path('api/calendar-events/', views.calendar_events_api, name='calendar_events_api'),
    path('api/update-block-time/', views.update_block_time_api, name='update_block_time_api'),

    # Task actions
    path('task/<int:task_id>/toggle/', views.toggle_task_status, name='toggle_task_status'),
    path('task/<int:task_id>/delete/', views.delete_task, name='delete_task'),

    # Lịch bận cố định (Recurring)
    path('recurring/', views.recurring_schedule_list, name='recurring_list'),
    path('recurring/<int:id>/delete/', views.delete_recurring, name='delete_recurring'),

    # Kích hoạt thuật toán
    path('auto-schedule/', views.trigger_auto_schedule, name='trigger_auto_schedule'),
    # Thêm vào danh sách urlpatterns trong planner/urls.py:
    path('pomodoro/', views.pomodoro_view, name='pomodoro_view'),
    path('api/save-pomodoro/', views.save_pomodoro_api, name='save_pomodoro_api'),

    path('ai-assistant/', views.ai_assistant_view, name='ai_assistant_view'),
]