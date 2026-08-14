"""通知服务：邮件 + 后端调度。

为避免硬依赖，前端浏览器通知在前端处理；这里实现邮件通知与扫描逻辑。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import List

import aiosmtplib
from loguru import logger
from sqlmodel import Session, select

from ..config import settings
from ..models.event import EventIndex, NotifyLog, Setting as SettingModel


def _resolve_smtp() -> dict:
    """读取最新 SMTP 配置（数据库 > 环境变量）。"""
    cfg = {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "use_ssl": settings.smtp_use_ssl,
        "user": settings.smtp_user,
        "pass": settings.smtp_pass,
        "from": settings.smtp_from,
    }
    try:
        with Session(__import__("..database", fromlist=["engine"]).engine) as s:
            for key in ("smtp_host", "smtp_port", "smtp_use_ssl", "smtp_user", "smtp_pass", "smtp_from"):
                row = s.exec(select(SettingModel).where(SettingModel.key == key)).first()
                if row and row.value:
                    if key == "smtp_port":
                        try:
                            cfg["port"] = int(row.value)
                        except Exception:
                            pass
                    elif key == "smtp_use_ssl":
                        cfg["use_ssl"] = row.value.lower() in ("1", "true", "yes")
                    else:
                        cfg[key.replace("smtp_", "")] = row.value
    except Exception:
        pass
    return cfg


def is_smtp_configured() -> bool:
    cfg = _resolve_smtp()
    return bool(cfg.get("host") and cfg.get("user") and cfg.get("pass"))


async def send_email(to: str, subject: str, body: str) -> None:
    """发送一封邮件。"""
    cfg = _resolve_smtp()
    if not (cfg.get("host") and cfg.get("user")):
        raise RuntimeError("SMTP not configured")

    msg = EmailMessage()
    msg["From"] = cfg.get("from") or cfg["user"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if cfg.get("use_ssl"):
        await aiosmtplib.send(
            msg,
            hostname=cfg["host"],
            port=cfg["port"],
            username=cfg["user"],
            password=cfg["pass"],
            use_tls=True,
        )
    else:
        await aiosmtplib.send(
            msg,
            hostname=cfg["host"],
            port=cfg["port"],
            username=cfg["user"],
            password=cfg["pass"],
            start_tls=True,
        )


def _reminder_key(event_id: str, type_: str, offset_minutes: int) -> str:
    return f"{event_id}:{type_}:{offset_minutes}"


async def scan_pending_emails() -> int:
    """扫描应当发送邮件提醒的活动，返回发送数量。"""
    if not is_smtp_configured():
        return 0

    from ..database import engine

    sent = 0
    now = datetime.utcnow()

    with Session(engine) as session:
        # 取未来 7 天内的活动
        upcoming = list(
            session.exec(
                select(EventIndex).where(
                    EventIndex.status == "planned",
                    EventIndex.start_at >= now,
                )
            ).all()
        )

        for idx in upcoming:
            try:
                reminders = json.loads(idx.reminders_json) if idx.reminders_json else []
            except Exception:
                continue

            for r in reminders:
                if r.get("type") != "email":
                    continue
                email_to = r.get("email")
                offset = int(r.get("offset_minutes", 0))
                if not email_to or offset < 0:
                    continue

                trigger_at = idx.start_at - timedelta(minutes=offset)
                # 容忍窗口：[trigger_at - 5min, trigger_at + 5min]
                if not (trigger_at - timedelta(minutes=5) <= now <= trigger_at + timedelta(minutes=5)):
                    continue

                key = _reminder_key(idx.id, "email", offset)
                # 24h 内去重
                recent = session.exec(
                    select(NotifyLog).where(
                        NotifyLog.reminder_key == key,
                        NotifyLog.sent_at >= now - timedelta(hours=24),
                    )
                ).first()
                if recent:
                    continue

                try:
                    subject = f"[MarkTheDate] 提醒：{idx.title}"
                    body = (
                        f"活动: {idx.title}\n"
                        f"开始时间: {idx.start_at.isoformat()}\n"
                        f"提前 {offset} 分钟提醒\n\n"
                        f"MarkTheDate"
                    )
                    await send_email(email_to, subject, body)
                    session.add(
                        NotifyLog(event_id=idx.id, channel="email", reminder_key=key, success=True)
                    )
                    sent += 1
                except Exception as e:
                    logger.exception("Email send failed: {}", e)
                    session.add(
                        NotifyLog(
                            event_id=idx.id,
                            channel="email",
                            reminder_key=key,
                            success=False,
                            error=str(e),
                        )
                    )

        session.commit()
    return sent


def get_pending_browser_notifications() -> List[dict]:
    """计算当前应当推送的浏览器通知（前端用）。"""
    from ..database import engine

    now = datetime.utcnow()
    pending: List[dict] = []
    with Session(engine) as session:
        upcoming = list(
            session.exec(
                select(EventIndex).where(
                    EventIndex.status == "planned",
                    EventIndex.start_at >= now - timedelta(minutes=1),
                )
            ).all()
        )
        for idx in upcoming:
            try:
                reminders = json.loads(idx.reminders_json) if idx.reminders_json else []
            except Exception:
                continue
            for r in reminders:
                if r.get("type") != "browser":
                    continue
                offset = int(r.get("offset_minutes", 0))
                trigger_at = idx.start_at - timedelta(minutes=offset)
                if not (trigger_at - timedelta(minutes=5) <= now <= trigger_at + timedelta(minutes=5)):
                    continue
                key = _reminder_key(idx.id, "browser", offset)
                # 24h 内去重
                recent = session.exec(
                    select(NotifyLog).where(
                        NotifyLog.reminder_key == key,
                        NotifyLog.sent_at >= now - timedelta(hours=24),
                    )
                ).first()
                if recent:
                    continue
                pending.append(
                    {
                        "event_id": idx.id,
                        "event_title": idx.title,
                        "event_start": idx.start_at.isoformat(),
                        "reminder_type": "browser",
                        "reminder_key": key,
                        "trigger_at": trigger_at.isoformat(),
                        "offset_minutes": offset,
                    }
                )
    return pending