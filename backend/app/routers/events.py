"""活动 CRUD API。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from ..database import get_session
from ..schemas.event import EventCreate, EventOut, EventSummary, EventUpdate
from ..services import file_manager

router = APIRouter(prefix="/api/events", tags=["events"])


def _summary(idx, session: Session) -> EventSummary:
    """从索引构造摘要。"""
    import json as _json

    tags = []
    try:
        tags = _json.loads(idx.tags_json) if idx.tags_json else []
    except Exception:
        pass
    return EventSummary(
        id=idx.id,
        title=idx.title,
        start=idx.start_at,
        end=idx.end_at,
        all_day=idx.all_day,
        status=idx.status,
        tags=tags,
        color=idx.color,
    )


@router.get("", response_model=List[EventSummary])
def list_events(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    session: Session = Depends(get_session),
):
    rows = file_manager.list_events(
        session,
        status=status,
        tag=tag,
        date_from=date_from,
        date_to=date_to,
    )
    return [_summary(r, session) for r in rows]


@router.post("", response_model=EventOut, status_code=201)
def create_event(payload: EventCreate, session: Session = Depends(get_session)):
    return file_manager.create_event(session, payload)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, session: Session = Depends(get_session)):
    evt = file_manager.read_event(session, event_id)
    if not evt:
        raise HTTPException(404, "Event not found")
    return evt


@router.put("/{event_id}", response_model=EventOut)
def update_event(
    event_id: str, payload: EventUpdate, session: Session = Depends(get_session)
):
    evt = file_manager.update_event(session, event_id, payload)
    if not evt:
        raise HTTPException(404, "Event not found")
    return evt


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: str, session: Session = Depends(get_session)):
    ok = file_manager.delete_event(session, event_id)
    if not ok:
        raise HTTPException(404, "Event not found")
    return None