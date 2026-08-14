"""通知相关 schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PendingNotification(BaseModel):
    """一条待推送的通知。"""

    event_id: str
    event_title: str
    event_start: datetime
    reminder_type: Literal["browser", "email"]
    reminder_key: str  # 用于 ack
    trigger_at: datetime  # 实际触发时间
    offset_minutes: int


class NotifyAckRequest(BaseModel):
    """前端确认通知已送达/已读。"""

    reminder_key: str