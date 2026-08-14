"""通知 API。"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models.event import NotifyLog
from ..schemas.notify import NotifyAckRequest, PendingNotification
from ..services import notifier


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/pending", response_model=List[PendingNotification])
def pending_notifications(session: Session = Depends(get_session)):
    items = notifier.get_pending_browser_notifications()
    return [PendingNotification(**i) for i in items]


@router.post("/ack", status_code=204)
def ack_notification(payload: NotifyAckRequest, session: Session = Depends(get_session)):
    """前端确认通知已被消费，写入日志避免重复。"""
    log = NotifyLog(
        event_id=payload.reminder_key.split(":", 1)[0],
        channel="browser",
        reminder_key=payload.reminder_key,
        success=True,
    )
    session.add(log)
    session.commit()
    return None


@router.post("/scan-emails")
async def scan_emails():
    """手动触发一次邮件扫描（调试用）。"""
    n = await notifier.scan_pending_emails()
    return {"sent": n}