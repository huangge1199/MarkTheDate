"""设置相关 schemas。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SettingsOut(BaseModel):
    """前端读取设置（敏感字段脱敏）。"""

    ai_provider: str = "openai"
    ai_base_url: str = ""
    ai_model: str = ""
    ai_api_key_set: bool = False  # 只回显是否设置
    ollama_base_url: str = ""
    ollama_model: str = ""

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_from: str = ""
    smtp_configured: bool = False

    notify_poll_interval_seconds: int = 60


class SettingsUpdate(BaseModel):
    """更新设置（所有字段可选）。"""

    ai_provider: Optional[str] = None
    ai_base_url: Optional[str] = None
    ai_api_key: Optional[str] = None  # 传空字符串表示清空
    ai_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None

    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_use_ssl: Optional[bool] = None
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    smtp_from: Optional[str] = None

    notify_poll_interval_seconds: Optional[int] = None