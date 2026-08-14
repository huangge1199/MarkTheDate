"""活动 Pydantic schemas（API I/O 模型）。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class Reminder(BaseModel):
    """单条提醒规则。"""

    type: Literal["browser", "email"] = "browser"
    offset_minutes: int = Field(default=60, ge=0, description="活动开始前多少分钟提醒")
    email: Optional[str] = Field(default=None, description="email 类型时使用的收件人")


class EventBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    start: datetime
    end: Optional[datetime] = None
    all_day: bool = False
    reminders: List[Reminder] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    color: Optional[str] = None
    status: Literal["planned", "ongoing", "done", "cancelled"] = "planned"
    source_url: Optional[HttpUrl] = None


class EventCreate(EventBase):
    """新建活动。"""

    content: str = Field(default="", description="Markdown 正文")
    slug: Optional[str] = Field(default=None, description="文件名 slug，不传则自动生成")


class EventUpdate(BaseModel):
    """更新活动（所有字段可选）。"""

    title: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    all_day: Optional[bool] = None
    reminders: Optional[List[Reminder]] = None
    tags: Optional[List[str]] = None
    color: Optional[str] = None
    status: Optional[Literal["planned", "ongoing", "done", "cancelled"]] = None
    source_url: Optional[HttpUrl] = None
    content: Optional[str] = None


class EventOut(BaseModel):
    """活动详情输出。"""

    id: str
    title: str
    start: datetime
    end: Optional[datetime]
    all_day: bool
    status: str
    reminders: List[Reminder]
    tags: List[str]
    color: Optional[str]
    source_url: Optional[str]
    content: str
    file_path: str
    created_at: Optional[datetime] = None
    updated_at: datetime


class EventSummary(BaseModel):
    """活动摘要（列表用，不含正文）。"""

    id: str
    title: str
    start: datetime
    end: Optional[datetime]
    all_day: bool
    status: str
    tags: List[str]
    color: Optional[str]


class CalendarDay(BaseModel):
    """日历某一天的事件分组。"""

    date: str  # YYYY-MM-DD
    events: List[EventSummary]


class CalendarMonth(BaseModel):
    """整月日历视图。"""

    year: int
    month: int
    days: List[CalendarDay]