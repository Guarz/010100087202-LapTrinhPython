# planner/ai_assistant.py
import json
import os
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import PomodoroLog, ScheduleBlock
from .risk import assess_user_tasks


def _today_blocks(user, now):
    local_now = timezone.localtime(now)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return list(
        ScheduleBlock.objects
        .filter(user=user, start_time__gte=start, start_time__lt=end)
        .order_by('start_time')
    )


def build_context(user, now=None):
    """Tổng hợp dữ liệu dùng cho cả AI và phân tích dự phòng."""
    now = now or timezone.now()
    risks = assess_user_tasks(user, now)
    week_ago = now - timedelta(days=7)
    recent_pomo = PomodoroLog.objects.filter(
        user=user, start_time__gte=week_ago,
    ).exclude(status='deferred').filter(completed=True)
    pomo_minutes = sum(
        (p.actual_seconds // 60) if p.actual_seconds else p.duration_minutes
        for p in recent_pomo
    )
    return {
        'now': now,
        'risks': risks,
        'today_blocks': _today_blocks(user, now),
        'pomo_count': recent_pomo.count(),
        'pomo_minutes': pomo_minutes,
    }


def _fallback_insights(ctx):
    risks = ctx['risks']
    blocks = ctx['today_blocks']
    high = [(t, r) for t, r in risks if r.level == 'high']
    medium = [(t, r) for t, r in risks if r.level == 'medium']
    total_remaining = sum(r.remaining_minutes for _, r in risks)

    if blocks:
        first = blocks[0]
        plan = (
            f"Hôm nay có {len(blocks)} khối lịch, bắt đầu với "
            f"\"{first.title}\" lúc {timezone.localtime(first.start_time):%H:%M}."
        )
    else:
        plan = 'Hôm nay chưa có khối lịch nào — hãy bấm "Tự động lập lịch tuần".'

    summary = (
        f"Bạn còn {len(risks)} nhiệm vụ mở, tổng khoảng "
        f"{total_remaining // 60} giờ {total_remaining % 60} phút cần học. {plan}"
    )
    if risks:
        top_task, top_risk = risks[0]
        summary += f" Ưu tiên số 1: \"{top_task.title}\" ({top_risk.score}/100 điểm rủi ro)."

    warnings = [
        f"{t.title}: {r.score}/100 — {r.reasons[0] if r.reasons else r.label}"
        for t, r in (high + medium)[:3]
    ]

    if ctx['pomo_count'] == 0:
        advice = 'Tuần này bạn chưa hoàn thành phiên Pomodoro nào. Hãy bắt đầu bằng 2 phiên 25 phút cho nhiệm vụ rủi ro cao nhất.'
    else:
        advice = (
            f"7 ngày qua bạn hoàn thành {ctx['pomo_count']} phiên ({ctx['pomo_minutes']} phút). "
            'Duy trì tối thiểu 4 phiên mỗi ngày và học nhiệm vụ rủi ro cao vào đầu buổi.'
        )

    return {
        'daily_summary': summary,
        'risk_warnings': warnings,
        'habit_advice': advice,
        'is_ai_generated': False,
    }


def analyze_schedule_with_ai(user, now=None):
    """
    1. Tổng hợp: task + điểm rủi ro, lịch hôm nay, Pomodoro 7 ngày.
    2. Có OPENAI_API_KEY: gửi ngữ cảnh cho OpenAI để tóm tắt ngày.
    3. Không có key hoặc lỗi: trả về phân tích dự phòng (không làm hỏng trang).
    """
    ctx = build_context(user, now)
    fallback = _fallback_insights(ctx)

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return fallback

    tasks_data = [
        {
            'title': t.title,
            'subject': t.subject_name or 'Chung',
            'deadline': timezone.localtime(t.deadline).strftime('%H:%M %d/%m/%Y'),
            'remaining_minutes': r.remaining_minutes,
            'risk_score': r.score,
            'risk_reasons': r.reasons,
        }
        for t, r in ctx['risks'][:10]
    ]
    blocks_data = [
        {
            'title': b.title,
            'start': timezone.localtime(b.start_time).strftime('%H:%M'),
            'end': timezone.localtime(b.end_time).strftime('%H:%M'),
        }
        for b in ctx['today_blocks']
    ]

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = (
            'Phân tích dữ liệu học tập của sinh viên hôm nay.\n'
            f'- Nhiệm vụ kèm điểm rủi ro trễ hạn (0-100): {json.dumps(tasks_data, ensure_ascii=False)}\n'
            f'- Lịch hôm nay: {json.dumps(blocks_data, ensure_ascii=False)}\n'
            f"- Pomodoro 7 ngày: {ctx['pomo_count']} phiên, {ctx['pomo_minutes']} phút.\n\n"
            'Trả về JSON: {"daily_summary": "tóm tắt ngày + phân bổ thời gian cụ thể theo giờ", '
            '"risk_warnings": ["1-3 cảnh báo cụ thể kèm tên nhiệm vụ"], '
            '"habit_advice": "1 lời khuyên thực tế"}'
        )
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {'role': 'system', 'content': 'Bạn là cố vấn lập kế hoạch học tập. Trả lời bằng tiếng Việt, JSON thuần.'},
                {'role': 'user', 'content': prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.5,
        )
        result = json.loads(response.choices[0].message.content)
        return {
            'daily_summary': result.get('daily_summary') or fallback['daily_summary'],
            'risk_warnings': result.get('risk_warnings') or fallback['risk_warnings'],
            'habit_advice': result.get('habit_advice') or fallback['habit_advice'],
            'is_ai_generated': True,
        }
    except Exception as exc:  # noqa: BLE001 - AI chỉ là tính năng hỗ trợ
        fallback['ai_error'] = str(exc)
        return fallback
