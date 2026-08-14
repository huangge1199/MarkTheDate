"""应用配置管理，基于 pydantic-settings 从 .env 加载。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent

# 默认值；用户可以在 .env 中以逗号分隔字符串形式覆盖（无需 JSON 包裹）
_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://localhost,http://127.0.0.1:3000"


def _parse_csv(value: str) -> List[str]:
    """把逗号分隔字符串切分为列表。"""
    if not value:
        return []
    return [s.strip() for s in value.split(",") if s.strip()]


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

    # 注意：.env 中的 CORS_ORIGINS 用逗号分隔字符串，如
    # CORS_ORIGINS=http://localhost:3000,http://localhost
    # 这里用 str 接收，在 cors_origins_list 属性里再切分。
    # 原因：pydantic-settings 的 DotEnvSource 默认会把 List[str] 当 JSON 解析，
    # 而用户写的是非 JSON 的纯字符串，会触发 JSONDecodeError。
    cors_origins: str = _DEFAULT_CORS_ORIGINS

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

    @property
    def cors_origins_list(self) -> List[str]:
        """返回 cors_origins 的列表形式，供 CORS 中间件使用。"""
        return _parse_csv(self.cors_origins)

    def ensure_dirs(self) -> None:
        """确保数据目录存在。"""
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()