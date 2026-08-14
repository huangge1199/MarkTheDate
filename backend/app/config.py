"""应用配置管理，基于 pydantic-settings 从 .env 加载。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """全局配置。"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 服务
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost",
        "http://127.0.0.1:5173",
    ]

    # AI
    ai_provider: str = "openai"  # openai | ollama
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # 邮件
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_use_ssl: bool = True
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""

    # 存储
    events_dir: Path = BASE_DIR / "data" / "events"
    db_path: Path = BASE_DIR / "data" / "markthedate.db"

    def ensure_dirs(self) -> None:
        """确保数据目录存在。"""
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()