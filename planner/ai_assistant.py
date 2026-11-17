# planner/ai_assistant.py
import json
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


GEMINI_OPENAI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/'

SYSTEM_PROMPT = (
    'Bạn là cố vấn lập kế hoạch học tập cho sinh viên Việt Nam. '
    'Trả lời bằng tiếng Việt, ngắn gọn, cụ thể theo giờ và tên nhiệm vụ. '
    'Chỉ dựa trên dữ liệu được cung cấp, không bịa thêm nhiệm vụ. '
    'Chỉ trả về một đối tượng JSON thuần, không markdown.'
)


def get_ai_provider():
    """Chọn nhà cung cấp AI từ cấu hình; None nếu chưa cấu hình."""
    if settings.AI_BASE_URL:
        return {
            'name': 'Ollama/tùy chỉnh',
            'base_url': settings.AI_BASE_URL,
            # Ollama không kiểm tra key nhưng SDK openai bắt buộc có giá trị
            'api_key': settings.AI_API_KEY or 'ollama',
            'model': settings.AI_MODEL or 'qwen2.5:7b',
        }
    if settings.GEMINI_API_KEY:
        return {
            'name': 'Gemini',
            'base_url': GEMINI_OPENAI_BASE_URL,
            'api_key': settings.GEMINI_API_KEY,
            'model': settings.AI_MODEL or 'gemini-flash-lite-latest',
        }
    if settings.OPENAI_API_KEY:
        return {
            'name': 'OpenAI',
            'base_url': None,
            'api_key': settings.OPENAI_API_KEY,
            'model': settings.AI_MODEL or 'gpt-4o-mini',
        }
    return None


def _build_prompt(ctx):
    tasks_data = [
        {
            'title': t.title,
            'subject': t.subject_name or (t.course.name if t.course_id else 'Chung'),
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
    return (
        f"Bây giờ là {timezone.localtime(ctx['now']):%H:%M %d/%m/%Y}. Phân tích dữ liệu học tập hôm nay.\n"
        f'- Nhiệm vụ kèm điểm rủi ro trễ hạn (0-100): {json.dumps(tasks_data, ensure_ascii=False)}\n'
        f'- Lịch hôm nay: {json.dumps(blocks_data, ensure_ascii=False)}\n'
        f"- Pomodoro 7 ngày: {ctx['pomo_count']} phiên, {ctx['pomo_minutes']} phút.\n\n"
        'Trả về JSON đúng 3 khóa: {"daily_summary": "tóm tắt việc cần làm hôm nay và phân bổ thời gian '
        'cụ thể theo khung giờ", "risk_warnings": ["1-3 cảnh báo cụ thể, nêu tên nhiệm vụ và lý do"], '
        '"habit_advice": "1 lời khuyên thực tế về thói quen học dựa trên số liệu Pomodoro"}'
    )


def _parse_json(text):
    """Model nhỏ (Ollama) đôi khi bọc JSON trong ```json ... ```; bóc ra trước khi parse."""
    text = (text or '').strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    start, end = text.find('{'), text.rfind('}')
    return json.loads(text[start:end + 1] if start != -1 else text)


def analyze_schedule_with_ai(user, now=None):
    """
    1. Tổng hợp: task + điểm rủi ro, lịch hôm nay, Pomodoro 7 ngày.
    2. Có cấu hình AI (Ollama / Gemini / OpenAI): gửi ngữ cảnh qua API chuẩn
       OpenAI, yêu cầu trả JSON để tóm tắt ngày.
    3. Chưa cấu hình, máy chủ AI tắt (VD Colab hết phiên) hoặc lỗi: trả về
       phân tích dự phòng, trang vẫn hoạt động.
    """
    ctx = build_context(user, now)
    fallback = _fallback_insights(ctx)

    provider = get_ai_provider()
    if provider is None:
        return fallback

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=provider['api_key'],
            base_url=provider['base_url'],
            timeout=settings.AI_TIMEOUT_SECONDS,
            max_retries=2,  # Gemini đôi khi trả 503 khi quá tải
        )
        response = client.chat.completions.create(
            model=provider['model'],
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': _build_prompt(ctx)},
            ],
            response_format={'type': 'json_object'},
            temperature=0.5,
        )
        result = _parse_json(response.choices[0].message.content)
        warnings = result.get('risk_warnings') or []
        if isinstance(warnings, str):
            warnings = [warnings]
        return {
            'daily_summary': result.get('daily_summary') or fallback['daily_summary'],
            'risk_warnings': warnings[:3] or fallback['risk_warnings'],
            'habit_advice': result.get('habit_advice') or fallback['habit_advice'],
            'is_ai_generated': True,
            'ai_provider': f"{provider['name']} · {provider['model']}",
        }
    except Exception as exc:  # noqa: BLE001 - AI chỉ là tính năng hỗ trợ
        fallback['ai_error'] = str(exc)
        fallback['ai_provider'] = f"{provider['name']} · {provider['model']}"
        return fallback
