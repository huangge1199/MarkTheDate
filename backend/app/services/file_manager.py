"""Markdown 文件管理器。

负责将活动持久化为 .md 文件，并同步 SQLite 索引。
文件名格式：YYYY/YYYY-MM-DD_slug.md
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import frontmatter
import ulid

from ..config import settings
from ..models.event import EventIndex
from ..schemas.event import EventCreate, EventOut, EventUpdate, Reminder
from sqlmodel import Session


SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)


def _slugify(text: str, max_len: int = 50) -> str:
    """生成文件名 slug。"""
    s = SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:max_len] or "event"


def _to_naive_utc(dt: datetime) -> datetime:
    """统一为 naive UTC 用于 SQLite 存储比较。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _file_path_for(start: datetime, slug: str) -> Path:
    """根据起始时间和 slug 生成文件路径。"""
    year = start.year if not start.tzinfo else start.astimezone().year
    year_dir = settings.events_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    date_part = start.strftime("%Y-%m-%d")
    return year_dir / f"{date_part}_{slug}.md"


def _serialise(value) -> str:
    """JSON 序列化，统一处理中文/日期。"""
    return json.dumps(value, ensure_ascii=False, default=str)


def _deserialise(raw: Optional[str], default):
    """JSON 反序列化。"""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _meta_to_dict(meta: dict) -> dict:
    """将 frontmatter meta 转储为可序列化 dict。"""
    out = {}
    for k, v in meta.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _event_to_frontmatter(data: EventCreate | EventUpdate, existing_meta: Optional[dict] = None) -> dict:
    """生成 frontmatter dict。"""
    meta = dict(existing_meta or {})
    now = datetime.now()

    meta.setdefault("id", str(ulid.new()))
    meta["title"] = data.title if isinstance(data, EventCreate) else (data.title or meta.get("title", ""))
    meta["start"] = (data.start if isinstance(data, EventCreate) else data.start) or meta.get("start")
    meta["end"] = (data.end if isinstance(data, EventCreate) else data.end) or meta.get("end")
    meta["all_day"] = (data.all_day if isinstance(data, EventCreate) else data.all_day) if isinstance(data, EventCreate) else (data.all_day if data.all_day is not None else meta.get("all_day", False))
    meta["reminders"] = [r.model_dump() for r in (data.reminders if isinstance(data, EventCreate) else (data.reminders or []))] if (isinstance(data, EventCreate) or (data.reminders is not None)) else meta.get("reminders", [])
    meta["tags"] = (data.tags if isinstance(data, EventCreate) else (data.tags or [])) if (isinstance(data, EventCreate) or data.tags is not None) else meta.get("tags", [])
    meta["status"] = (data.status if isinstance(data, EventCreate) else (data.status or meta.get("status", "planned")))
    meta.setdefault("created_at", meta.get("created_at") or now)
    meta["updated_at"] = now

    if isinstance(data, EventCreate) and data.color:
        meta["color"] = data.color
    elif isinstance(data, EventUpdate) and data.color is not None:
        meta["color"] = data.color

    if isinstance(data, EventCreate) and data.source_url:
        meta["source_url"] = str(data.source_url)
    elif isinstance(data, EventUpdate) and data.source_url is not None:
        meta["source_url"] = str(data.source_url) if data.source_url else None

    return meta


def _build_event_out(file_path: Path, meta: dict, content: str) -> EventOut:
    """从 frontmatter + content 构建 EventOut。"""
    reminders = [Reminder(**r) for r in meta.get("reminders", []) or []]
    tags = meta.get("tags", []) or []

    return EventOut(
        id=meta["id"],
        title=meta["title"],
        start=meta["start"],
        end=meta.get("end"),
        all_day=bool(meta.get("all_day", False)),
        status=meta.get("status", "planned"),
        reminders=reminders,
        tags=tags,
        color=meta.get("color"),
        source_url=meta.get("source_url"),
        content=content,
        file_path=str(file_path.relative_to(settings.events_dir.parent)),
        created_at=meta.get("created_at"),
        updated_at=meta.get("updated_at") or datetime.now(),
    )


def create_event(session: Session, payload: EventCreate) -> EventOut:
    """创建活动：写 .md + 入库索引。"""
    slug = payload.slug or _slugify(payload.title)
    file_path = _file_path_for(payload.start, slug)

    # 同名冲突时追加 ULID 后缀
    if file_path.exists():
        slug = f"{slug}-{str(ulid.new())[:6].lower()}"
        file_path = _file_path_for(payload.start, slug)

    meta = _event_to_frontmatter(payload)
    meta["id"] = str(ulid.new())
    post = frontmatter.Post(payload.content or "", **meta)
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    # 同步索引
    idx = EventIndex(
        id=meta["id"],
        file_path=str(file_path),
        title=meta["title"],
        start_at=_to_naive_utc(meta["start"]),
        end_at=_to_naive_utc(meta["end"]) if meta.get("end") else None,
        all_day=bool(meta.get("all_day", False)),
        status=meta.get("status", "planned"),
        reminders_json=_serialise([r.model_dump() for r in payload.reminders]),
        source_url=meta.get("source_url"),
        tags_json=_serialise(payload.tags),
        color=meta.get("color"),
        updated_at=datetime.now(),
    )
    session.add(idx)
    session.commit()

    return _build_event_out(file_path, meta, payload.content or "")


def read_event(session: Session, event_id: str) -> Optional[EventOut]:
    """读取活动详情。"""
    idx = session.get(EventIndex, event_id)
    if not idx:
        return None
    file_path = Path(idx.file_path)
    if not file_path.exists():
        return None
    post = frontmatter.load(file_path)
    meta = _meta_to_dict(post.metadata)
    return _build_event_out(file_path, meta, post.content)


def update_event(session: Session, event_id: str, payload: EventUpdate) -> Optional[EventOut]:
    """更新活动。"""
    idx = session.get(EventIndex, event_id)
    if not idx:
        return None

    file_path = Path(idx.file_path)
    post = frontmatter.load(file_path)
    existing_meta = _meta_to_dict(post.metadata)
    existing_content = post.content

    new_meta = _event_to_frontmatter(payload, existing_meta=existing_meta)

    # 保留 id/created_at
    new_meta["id"] = existing_meta["id"]
    new_meta.setdefault("created_at", existing_meta.get("created_at"))

    new_content = payload.content if payload.content is not None else existing_content

    # 时间变了可能需要重命名文件
    new_start_raw = new_meta["start"]
    new_start = new_start_raw if isinstance(new_start_raw, datetime) else datetime.fromisoformat(str(new_start_raw))
    new_file_path = _file_path_for(new_start, file_path.stem.split("_", 1)[1] if "_" in file_path.stem else file_path.stem)

    if new_file_path != file_path:
        new_file_path.parent.mkdir(parents=True, exist_ok=True)
        post2 = frontmatter.Post(new_content, **new_meta)
        new_file_path.write_text(frontmatter.dumps(post2), encoding="utf-8")
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass
        file_path = new_file_path
    else:
        post2 = frontmatter.Post(new_content, **new_meta)
        file_path.write_text(frontmatter.dumps(post2), encoding="utf-8")

    # 同步索引
    idx.file_path = str(file_path)
    idx.title = new_meta["title"]
    idx.start_at = _to_naive_utc(new_meta["start"])
    idx.end_at = _to_naive_utc(new_meta["end"]) if new_meta.get("end") else None
    idx.all_day = bool(new_meta.get("all_day", False))
    idx.status = new_meta.get("status", "planned")
    idx.reminders_json = _serialise(new_meta.get("reminders", []))
    idx.tags_json = _serialise(new_meta.get("tags", []))
    idx.color = new_meta.get("color")
    idx.source_url = new_meta.get("source_url")
    idx.updated_at = datetime.now()
    session.add(idx)
    session.commit()

    return _build_event_out(file_path, new_meta, new_content)


def delete_event(session: Session, event_id: str) -> bool:
    """删除活动。"""
    idx = session.get(EventIndex, event_id)
    if not idx:
        return False
    file_path = Path(idx.file_path)
    try:
        if file_path.exists():
            file_path.unlink()
    except FileNotFoundError:
        pass
    session.delete(idx)
    session.commit()
    return True


def list_events(
    session: Session,
    *,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[EventIndex]:
    """列出活动索引（支持过滤）。"""
    from sqlmodel import select

    stmt = select(EventIndex)
    if status:
        stmt = stmt.where(EventIndex.status == status)
    if date_from:
        stmt = stmt.where(EventIndex.end_at == None) | stmt.where(EventIndex.end_at >= _to_naive_utc(date_from))  # type: ignore
        # 同时也要求 start_at <= date_to 之后在调用方做
    if date_to:
        stmt = stmt.where(EventIndex.start_at <= _to_naive_utc(date_to))  # type: ignore
    stmt = stmt.order_by(EventIndex.start_at)
    rows = list(session.exec(stmt).all())

    if tag:
        rows = [r for r in rows if tag in (_deserialise(r.tags_json, []) or [])]

    if date_from:
        df = _to_naive_utc(date_from)
        rows = [r for r in rows if (r.end_at or r.start_at) >= df]

    return rows


def read_event_content(event_id: str, session: Session) -> Optional[Tuple[str, str]]:
    """读取活动正文（用于 AI 优化），返回 (content, file_path)。"""
    idx = session.get(EventIndex, event_id)
    if not idx:
        return None
    file_path = Path(idx.file_path)
    if not file_path.exists():
        return None
    post = frontmatter.load(file_path)
    return post.content, str(file_path)


def write_event_content(event_id: str, session: Session, new_content: str) -> Optional[str]:
    """写入活动正文（AI 优化时调用），返回新 file_path。"""
    idx = session.get(EventIndex, event_id)
    if not idx:
        return None
    file_path = Path(idx.file_path)
    post = frontmatter.load(file_path)
    post.content = new_content
    if "updated_at" in post.metadata:
        post.metadata["updated_at"] = datetime.now()
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    idx.updated_at = datetime.now()
    session.add(idx)
    session.commit()
    return str(file_path)