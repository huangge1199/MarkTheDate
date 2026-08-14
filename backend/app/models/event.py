"""活动数据库模型（SQLite 索引）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class EventIndex(SQLModel, table=True):
    """活动索引表，存储在 SQLite 用于加速查询。

    Markdown 文件本身才是数据源。
    """

    __tablename__ = "events"

    id: str = Field(primary_key=True, index=True)
    file_path: str = Field(unique=True, index=True)
    title: str = Field(index=True)
    start_at: datetime = Field(index=True)
    end_at: Optional[datetime] = Field(default=None)
    all_day: bool = Field(default=False)
    status: str = Field(default="planned", index=True)
    reminders_json: Optional[str] = Field(default=None)
    source_url: Optional[str] = Field(default=None)
    tags_json: Optional[str] = Field(default=None)
    color: Optional[str] = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.now)


class NotifyLog(SQLModel, table=True):
    """通知发送日志，避免重复提醒。"""

    __tablename__ = "notify_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: str = Field(index=True)
    channel: str  # browser / email
    reminder_key: str  # 用于去重: f"{event_id}:{type}:{offset_minutes}"
    sent_at: datetime = Field(default_factory=datetime.now)
    success: bool = Field(default=True)
    error: Optional[str] = Field(default=None)


class Setting(SQLModel, table=True):
    """运行时设置（AI key、邮件配置等），可由前端动态修改。"""

    __tablename__ = "settings"

    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime = Field(default_factory=datetime.now)