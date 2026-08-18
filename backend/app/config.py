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

    # 存储后端：s3（默认，兼容 rustfs / MinIO / AWS S3）| local（本地 data/）
    storage_backend: str = "s3"
    storage_local_root: Path = BASE_DIR / "data"

    # SQLite 数据库 + URL 抓取临时目录仍在本地
    db_path: Path = BASE_DIR / "data" / "markthedate.db"
    tmp_dir: Path = BASE_DIR / "data" / "tmp"

    # S3 / rustfs 配置
    s3_endpoint_url: str = ""  # 如 http://localhost:9000
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "markthedate"
    s3_region: str = "us-east-1"
    s3_path_style: bool = True  # rustfs / MinIO 必须 True；AWS 默认 False
    s3_public_base_url: str = ""  # 若桶可公开访问或经过 CDN，可填此 URL 直链
    s3_presign_expires: int = 3600  # 预签名 URL 时效

    @property
    def fetch_tmp_dir(self) -> Path:
        """URL 抓取的临时文件目录（图片等，仅 local 模式使用）。"""
        return self.tmp_dir / "fetch"

    @property
    def cors_origins_list(self) -> List[str]:
        return _parse_csv(self.cors_origins)

    def ensure_dirs(self) -> None:
        """确保本地数据目录存在（数据库、抓取临时目录）。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.fetch_tmp_dir.mkdir(parents=True, exist_ok=True)
        if self.storage_backend == "local":
            self.storage_local_root.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()