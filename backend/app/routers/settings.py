"""设置 API：读写运行期配置（数据库覆盖环境变量）。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models.event import Setting as SettingModel
from ..schemas.settings import SettingsOut, SettingsUpdate


router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get(key: str, default: str = "") -> str:
    with Session(__import__("..database", fromlist=["engine"]).engine) as s:
        row = s.exec(select(SettingModel).where(SettingModel.key == key)).first()
        if row and row.value is not None:
            return row.value
    return default


def _set(key: str, value: str) -> None:
    from ..database import engine

    with Session(engine) as s:
        row = s.exec(select(SettingModel).where(SettingModel.key == key)).first()
        if row:
            row.value = value
            row.updated_at = datetime.now()
            s.add(row)
        else:
            s.add(SettingModel(key=key, value=value))
        s.commit()


@router.get("", response_model=SettingsOut)
def get_settings():
    return SettingsOut(
        ai_provider=_get("ai_provider", settings.ai_provider),
        ai_base_url=_get("ai_base_url", settings.ai_base_url),
        ai_model=_get("ai_model", settings.ai_model),
        ai_api_key_set=bool(_get("ai_api_key", settings.ai_api_key)),
        ollama_base_url=_get("ollama_base_url", settings.ollama_base_url),
        ollama_model=_get("ollama_model", settings.ollama_model),
        smtp_host=_get("smtp_host", settings.smtp_host),
        smtp_port=int(_get("smtp_port", str(settings.smtp_port))),
        smtp_user=_get("smtp_user", settings.smtp_user),
        smtp_from=_get("smtp_from", settings.smtp_from),
        smtp_configured=bool(_get("smtp_host", settings.smtp_host) and _get("smtp_user", settings.smtp_user)),
        notify_poll_interval_seconds=int(_get("notify_poll_interval_seconds", "60")),
    )


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate):
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is None:
            continue
        _set(k, "" if v is False and k in ("smtp_use_ssl",) else str(v))
    return get_settings()