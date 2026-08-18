"""AI 相关 schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class FetchRequest(BaseModel):
    """URL 抓取请求。"""

    url: HttpUrl


class FetchResponse(BaseModel):
    """URL 抓取结果（草稿事件）。"""

    title: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    all_day: bool = False
    tags: List[str] = Field(default_factory=list)
    source_url: str
    content: str = Field(default="", description="Markdown 格式的描述")
    raw_html_excerpt: str = Field(default="", description="原文片段，便于追溯")
    confidence: Literal["high", "medium", "low"] = "medium"
    # 抓取会话 id。前端拿到后可在保存事件时传给后端，
    # 由后端把临时图片搬到 events 目录；丢弃时直接删除该 session 目录。
    session_id: Optional[str] = None


class AIOptimizeRequest(BaseModel):
    """AI 优化请求。"""

    event_id: str
    instruction: Optional[str] = Field(
        default=None,
        description="可选的优化指令，如'更正式'、'翻译成英文'等",
    )


class AIOptimizeResponse(BaseModel):
    """AI 优化结果，返回 diff 用的前后内容。"""

    event_id: str
    before: str
    after: str
    diff_summary: Optional[str] = None


class AISuggestRequest(BaseModel):
    """根据正文 AI 提取元数据。"""

    content: str


class AISuggestResponse(BaseModel):
    """AI 建议的元数据。"""

    title: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    summary: Optional[str] = None