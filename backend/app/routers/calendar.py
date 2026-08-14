"""日历视图 API。"""
from __future__ import annotations

import json
from calendar import monthrange
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ..database import get_session
from ..models.event import EventIndex
from ..schemas.event import CalendarDay, CalendarMonth, EventSummary


router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("", response_model=CalendarMonth)
def get_calendar(
    year: int = Query(..., ge=1970, le=2999),
    month: int = Query(..., ge=1, le=12),
    session: Session = Depends(get_session),
):
    """返回指定年月的日历视图，每个日期包含当日（含跨天）的事件。"""
    days_in_month = monthrange(year, month)[1]
    start_of_month = datetime(year, month, 1)
    end_of_month = datetime(year, month, days_in_month, 23, 59, 59)

    stmt = select(EventIndex).where(
        EventIndex.start_at <= end_of_month
    ).where(
        # 跨天事件：end_at >= month_start
        (EventIndex.end_at == None) | (EventIndex.end_at >= start_of_month)  # type: ignore
    ).order_by(EventIndex.start_at)
    rows = list(session.exec(stmt).all())

    # 按天分组
    day_map: dict[str, list[EventSummary]] = {}
    for d in range(1, days_in_month + 1):
        day_map[f"{year:04d}-{month:02d}-{d:02d}"] = []

    for idx in rows:
        tags = []
        try:
            tags = json.loads(idx.tags_json) if idx.tags_json else []
        except Exception:
            pass
        summary = EventSummary(
            id=idx.id,
            title=idx.title,
            start=idx.start_at,
            end=idx.end_at,
            all_day=idx.all_day,
            status=idx.status,
            tags=tags,
            color=idx.color,
        )
        # 计算事件覆盖的日期
        s = idx.start_at
        e = idx.end_at or idx.start_at
        cur = datetime(s.year, s.month, s.day)
        end_d = datetime(e.year, e.month, e.day)
        while cur <= end_d:
            key = cur.strftime("%Y-%m-%d")
            if key in day_map:
                day_map[key].append(summary)
            cur += timedelta(days=1)

    days = [CalendarDay(date=k, events=v) for k, v in day_map.items()]
    return CalendarMonth(year=year, month=month, days=days)