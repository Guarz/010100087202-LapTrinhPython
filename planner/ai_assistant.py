# planner/ai_assistant.py
import os
import json
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Task, ScheduleBlock, PomodoroLog, UserProfile

def analyze_schedule_with_ai(user):
    """
    1. Tổng hợp dữ liệu: Task chưa xong, lịch bận tuần, nhật ký Pomodoro.
    2. Đánh giá rủi ro trễ hạn theo thuật toán định lượng.
    3. Gửi ngữ cảnh sang OpenAI API để phân tích chuyên sâu.
    """
    now = timezone.now()
    today = now.date()

    # A. Thu thập các task chưa hoàn thành
    pending_tasks = Task.objects.filter(
        user=user,
        status__in=['todo', 'in_progress']
    ).order_by('deadline')

    tasks_data = []
    total_estimated_minutes = 0
    overdue_risk_count = 0

    for t in pending_tasks:
        hours_left = (t.deadline - now).total_seconds() / 3600
        # Đánh giá sơ bộ: nếu thời gian còn lại trước hạn < thời lượng ước tính * 1.5
        is_risky = (hours_left > 0) and (hours_left * 60 < t.estimated_minutes * 1.5)
        if is_risky or hours_left <= 0:
            overdue_risk_count += 1

        total_estimated_minutes += t.estimated_minutes
        tasks_data.append({
            "title": t.title,
            "subject": t.subject_name or "Chung",
            "deadline": t.deadline.strftime("%H:%M %d/%m/%Y"),
            "estimated_minutes": t.estimated_minutes,
            "priority": "Cao" if t.priority == 1 else ("Vừa" if t.priority == 2 else "Thấp"),
            "hours_until_deadline": round(hours_left, 1)
        })

    # B. Thu thập thói quen học từ PomodoroLog (7 ngày gần nhất)
    week_ago = now - timedelta(days=7)
    recent_pomo = PomodoroLog.objects.filter(user=user, start_time__gte=week_ago, completed=True)
    total_pomo_minutes = sum(p.duration_minutes for p in recent_pomo)
    pomo_count = recent_pomo.count()

    # C. Kiểm tra API Key của OpenAI
    api_key = os.getenv("OPENAI_API_KEY")

    # Trường hợp chưa cấu hình API Key: Trả về phân tích Heuristic dự phòng (không làm crash app)
    if not api_key:
        return {
            "daily_summary": f"Hôm nay bạn có {len(tasks_data)} nhiệm vụ đang chờ xử lý với tổng thời lượng ước tính khoảng {total_estimated_minutes // 60} giờ {total_estimated_minutes % 60} phút.",
            "risk_warnings": [
                f"Phát hiện {overdue_risk_count} nhiệm vụ có nguy cơ trễ hạn hoặc thời gian gấp rút!" if overdue_risk_count > 0 else "Tiến độ hiện tại an toàn, chưa có deadline nguy hiểm."
            ],
            "habit_advice": f"Trong 7 ngày qua, bạn đã hoàn thành {pomo_count} phiên Pomodoro ({total_pomo_minutes} phút). Hãy duy trì tối thiểu 4 phiên mỗi ngày để đảm bảo hoàn thành bài tập.",
            "is_ai_generated": False
        }

    # D. Gọi OpenAI API (Structured JSON)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""
        Bạn là trợ lý học tập AI cá nhân cho sinh viên. Hãy phân tích dữ liệu thực tế sau đây:
        - Danh sách bài tập/deadline: {json.dumps(tasks_data, ensure_ascii=False)}
        - Lịch sử Pomodoro 7 ngày: {pomo_count} phiên hoàn thành, tổng cộng {total_pomo_minutes} phút tập trung.

        Yêu cầu trả về đúng định dạng JSON có cấu trúc sau (không kèm markdown ngoài JSON):
        {{
            "daily_summary": "Tóm tắt ngắn gọn việc ưu tiên cần làm trong ngày hôm nay",
            "risk_warnings": ["Danh sách 1-3 cảnh báo rủi ro trễ hạn cụ thể kèm tên môn"],
            "habit_advice": "1 lời khuyên thực tế để cải thiện thói quen học và phân bổ thời gian"
        }}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia cố vấn lập kế hoạch học tập. Trả về định dạng JSON thuần."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        result = json.loads(response.choices[0].message.content)
        result["is_ai_generated"] = True
        return result

    except Exception as e:
        return {
            "daily_summary": "Đang đồng bộ phân tích lịch học...",
            "risk_warnings": [f"Lỗi kết nối AI: {str(e)}"],
            "habit_advice": "Hãy ưu tiên giải quyết các bài tập có mức ưu tiên Cao trước.",
            "is_ai_generated": False
        }