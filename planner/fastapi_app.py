# planner/fastapi_app.py
"""
API PHỤ TRỢ BẰNG FASTAPI

Dùng chung thuật toán với Django (risk.calculate_risk, scheduler.plan_sessions)
nhưng là API thuần tính toán, không truy cập dữ liệu người dùng:
  GET  /api/v2/health
  POST /api/v2/risk        -> tính điểm rủi ro trễ hạn
  POST /api/v2/plan        -> xếp lịch thử cho danh sách task + khoảng trống
Tài liệu Swagger: /api/v2/docs

Chạy cùng Django: uvicorn core.asgi:application
"""
from datetime import datetime
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .risk import calculate_risk
from .scheduler import PlanTask, plan_sessions

api = FastAPI(
    title='AI Study Planner - API phụ trợ',
    version='1.0.0',
    docs_url='/docs',
    openapi_url='/openapi.json',
)


class RiskIn(BaseModel):
    hours_left: float
    estimated_minutes: int = Field(gt=0)
    focused_minutes: int = 0
    scheduled_minutes: int = 0
    priority: int = Field(2, ge=1, le=3)
    status: str = 'todo'


class RiskOut(BaseModel):
    score: int
    level: str
    label: str
    remaining_minutes: int
    reasons: List[str]


class PlanTaskIn(BaseModel):
    title: str
    minutes: int = Field(gt=0)
    deadline: datetime
    priority: int = Field(2, ge=1, le=3)


class SlotIn(BaseModel):
    start: datetime
    end: datetime


class PlanIn(BaseModel):
    tasks: List[PlanTaskIn]
    free_slots: List[SlotIn]


class SessionOut(BaseModel):
    title: str
    start: datetime
    end: datetime
    minutes: int


class PlanOut(BaseModel):
    sessions: List[SessionOut]
    unscheduled: dict


@api.get('/health')
def health():
    return {'status': 'ok'}


@api.post('/risk', response_model=RiskOut)
def risk(payload: RiskIn):
    result = calculate_risk(**payload.model_dump())
    return RiskOut(
        score=result.score,
        level=result.level,
        label=result.label,
        remaining_minutes=result.remaining_minutes,
        reasons=result.reasons,
    )


@api.post('/plan', response_model=PlanOut)
def plan(payload: PlanIn):
    tasks = [
        PlanTask(key=item.title, title=item.title, minutes=item.minutes,
                 deadline=item.deadline, priority=item.priority)
        for item in payload.tasks
    ]
    slots = sorted([[slot.start, slot.end] for slot in payload.free_slots])
    sessions, unscheduled = plan_sessions(tasks, slots)
    return PlanOut(
        sessions=[
            SessionOut(title=s.task.title, start=s.start, end=s.end, minutes=s.minutes)
            for s in sessions
        ],
        unscheduled=unscheduled,
    )
