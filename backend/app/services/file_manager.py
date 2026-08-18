"""Markdown 文件管理器。

负责将活动持久化为 .md 文件（通过 storage.Storage 抽象层），并同步 SQLite 索引。

存储布局（无论 local 还是 S3，object key 一致）：
  events/<year>/<slug>.md           活动 markdown 主份
  events/<year>/<slug>_files/<filename>   资产（图片等）

跨年活动只在 start 年份放主份；end / 中间年份不建 entry —— 前端始终通过
主份的 public URL（同一 URL）访问，避免 S3 不支持 junction 的问题。

EventIndex.file_path 存储 S3 key（形如 "events/2026/slug.md"），不是本地路径。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import frontmatter
import ulid
from loguru import logger
from sqlmodel import Session

from ..config import settings
from ..models.event import EventIndex
from ..schemas.event import EventCreate, EventOut, EventUpdate, Reminder
from .storage import Storage, get_storage


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


def _year_of(dt: datetime) -> int:
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.year


def _cross_years(start: datetime, end: Optional[datetime]) -> List[int]:
    if end is None:
        return [_year_of(start)]
    ys = _year_of(start)
    ye = _year_of(end)
    if ys == ye:
        return [ys]
    return list(range(ys, ye + 1))


# ---- key 推导 ----


def event_md_key(year: int, slug: str) -> str:
    return f"events/{year}/{slug}.md"


def event_files_prefix(year: int, slug: str) -> str:
    """资产目录前缀（含 trailing slash），可与 list_prefix / delete_prefix 配合。"""
    return f"events/{year}/{slug}_files/"


def event_md_key_from_index(idx: EventIndex) -> str:
    """从 EventIndex 取 md 的 object key。兼容历史相对路径。"""
    p = idx.file_path.replace("\\", "/")
    if p.startswith("events/"):
        return p
    # 历史：相对路径 'data/events/2026/x.md' → 去掉 'data/' 前缀
    if p.startswith("data/"):
        return p[len("data/") :]
    return p


# ---- 数据库 / 序列化 ----


def _list_tags_from_json(value: Optional[str]) -> List[str]:
    if not value:
        return []
    try:
        out = json.loads(value)
        if isinstance(out, list):
            return [str(x) for x in out]
    except Exception:
        return []
    return []


def _dump_tags(tags: Optional[Iterable[str]]) -> str:
    return json.dumps(list(tags or []), ensure_ascii=False)


def _reminders_from_dict(rm: Optional[List[dict]]) -> Optional[List[Reminder]]:
    if not rm:
        return None
    out: List[Reminder] = []
    for item in rm:
        try:
            out.append(Reminder(**item))
        except Exception:
            continue
    return out or None


def _build_event_out(
    file_key: str, meta: dict, content: str, *, created_at=None, updated_at=None
) -> EventOut:
    """根据 frontmatter meta + content 构造 EventOut。"""
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    reminders = _reminders_from_dict(meta.get("reminders")) or []
    start_raw = meta.get("start")
    end_raw = meta.get("end")
    start_at = _to_naive_utc(start_raw) if start_raw else datetime.now()
    end_at = _to_naive_utc(end_raw) if end_raw else None
    return EventOut(
        id=meta.get("id") or "",
        title=meta.get("title") or "",
        start=start_at,
        end=end_at,
        all_day=bool(meta.get("all_day", False)),
        status=meta.get("status", "planned"),
        reminders=reminders,
        tags=tags,
        color=meta.get("color"),
        source_url=meta.get("source_url"),
        content=content,
        file_path=file_key,
        created_at=created_at,
        updated_at=updated_at or meta.get("updated_at") or datetime.now(),
    )


# ---- 公共 API ----


def list_events(
    session: Session,
    *,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[EventIndex]:
    """从 SQLite 索引查询活动。"""
    stmt = select(EventIndex)
    if status:
        stmt = stmt.where(EventIndex.status == status)
    if date_from:
        stmt = stmt.where(EventIndex.start_at >= _to_naive_utc(date_from))
    if date_to:
        stmt = stmt.where(EventIndex.start_at <= _to_naive_utc(date_to))
    rows = list(session.exec(stmt).all())
    if tag:
        rows = [r for r in rows if tag in _list_tags_from_json(r.tags_json)]
    rows.sort(key=lambda r: (r.start_at, r.updated_at, r.id))
    return rows


def read_event(session: Session, event_id: str) -> Optional[EventOut]:
    """按 event_id 读活动（含正文）。"""
    idx = session.get(EventIndex, event_id)
    if not idx:
        return None
    return _read_event_from_idx(idx)


def read_event_content(event_id: str, session: Session) -> Optional[tuple[str, str]]:
    """返回 (content, file_key) 元组；找不到返回 None。"""
    idx = session.get(EventIndex, event_id)
    if not idx:
        return None
    out = _read_event_from_idx(idx)
    return out.content, out.file_path


def write_event_content(event_id: str, session: Session, new_content: str) -> Optional[str]:
    """只更新正文，返回新的 file_key。"""
    storage = get_storage()
    idx = session.get(EventIndex, event_id)
    if not idx:
        return None
    md_key = event_md_key_from_index(idx)
    try:
        old_bytes = storage.get_bytes(md_key)
    except FileNotFoundError:
        old_bytes = b""
    post = frontmatter.loads(old_bytes.decode("utf-8") if old_bytes else "")
    new_post = frontmatter.Post(new_content, **dict(post.metadata))
    storage.put_bytes(md_key, frontmatter.dumps(new_post).encode("utf-8"))
    return md_key


def _read_event_from_idx(idx: EventIndex) -> EventOut:
    storage = get_storage()
    key = event_md_key_from_index(idx)
    try:
        data = storage.get_bytes(key)
    except FileNotFoundError:
        logger.warning("event file not found in storage: {}", key)
        data = b""
    post = frontmatter.loads(data.decode("utf-8") if isinstance(data, bytes) else str(data))
    return _build_event_out(
        key,
        dict(post.metadata),
        post.content,
        updated_at=idx.updated_at,
    )


def create_event(session: Session, payload: EventCreate) -> EventOut:
    """创建活动：分配 ULID，写主份到 storage，建索引。"""
    storage = get_storage()
    eid = str(ulid.new())
    slug = payload.slug or _slugify(payload.title)
    year = _year_of(payload.start)
    md_key = event_md_key(year, slug)
    # 重名时加 ULID 后缀避免 key 冲突
    if storage.exists(md_key):
        md_key = f"events/{year}/{slug}-{eid[:8]}.md"

    def _str(v):
        if v is None:
            return None
        return str(v)

    meta = {
        "id": eid,
        "title": payload.title,
        "start": _to_naive_utc(payload.start),
        "end": _to_naive_utc(payload.end) if payload.end else None,
        "all_day": bool(payload.all_day),
        "status": payload.status,
        "tags": list(payload.tags or []),
        "color": payload.color,
        "source_url": _str(payload.source_url),
        "reminders": [r.model_dump(exclude_none=True) for r in (payload.reminders or [])],
    }
    meta = {k: v for k, v in meta.items() if v is not None and v != []}
    meta["all_day"] = bool(meta.get("all_day", False))
    post = frontmatter.Post(payload.content or "", **meta)
    storage.put_bytes(md_key, frontmatter.dumps(post).encode("utf-8"))

    idx = EventIndex(
        id=eid,
        title=payload.title,
        start_at=meta["start"],
        end_at=meta.get("end"),
        all_day=bool(meta["all_day"]),
        status=payload.status,
        tags_json=_dump_tags(payload.tags),
        color=payload.color,
        source_url=_str(payload.source_url),
        file_path=md_key,
    )
    session.add(idx)
    session.commit()
    session.refresh(idx)
    return _build_event_out(md_key, dict(post.metadata), post.content)


def update_event(
    session: Session, event_id: str, payload: EventUpdate
) -> Optional[EventOut]:
    """更新活动：start 跨年迁移主份 key；end 等字段变化更新 meta。"""
    storage = get_storage()
    idx = session.get(EventIndex, event_id)
    if not idx:
        return None

    old_key = event_md_key_from_index(idx)
    # 读旧 meta+content
    try:
        old_bytes = storage.get_bytes(old_key)
    except FileNotFoundError:
        old_bytes = b""
    old_post = frontmatter.loads(old_bytes.decode("utf-8") if old_bytes else "")
    old_meta: dict = dict(old_post.metadata)

    # 准备新 meta
    new_meta = dict(old_meta)
    new_content = old_post.content
    if payload.title is not None:
        new_meta["title"] = payload.title
    if payload.start is not None:
        new_meta["start"] = _to_naive_utc(payload.start)
    if payload.end is not None:
        new_meta["end"] = _to_naive_utc(payload.end)
    elif "end" in new_meta:
        del new_meta["end"]
    if payload.all_day is not None:
        new_meta["all_day"] = payload.all_day
    if payload.status is not None:
        new_meta["status"] = payload.status
    if payload.tags is not None:
        new_meta["tags"] = list(payload.tags)
    if payload.color is not None:
        new_meta["color"] = payload.color
    elif "color" in new_meta and payload.color is None:
        new_meta.pop("color", None)
    if payload.source_url is not None:
        new_meta["source_url"] = payload.source_url
    if payload.reminders is not None:
        new_meta["reminders"] = [r.model_dump(exclude_none=True) for r in payload.reminders]
    if payload.content is not None:
        new_content = payload.content

    new_start = new_meta["start"]
    new_end = new_meta.get("end")
    # slug 可能随 title 变
    new_slug = _slugify(new_meta["title"])
    new_year = _year_of(new_start)
    target_key = event_md_key(new_year, new_slug)
    if storage.exists(target_key) and target_key != old_key:
        target_key = f"events/{new_year}/{new_slug}-{event_id[:8]}.md"

    new_meta["id"] = event_id
    new_post = frontmatter.Post(new_content, **new_meta)
    new_bytes = frontmatter.dumps(new_post).encode("utf-8")

    # 写入新位置
    storage.put_bytes(target_key, new_bytes)
    # 删除旧位置
    if old_key != target_key:
        storage.delete(old_key)
        # 主份迁移后，_files 资产前缀也变了 — 把旧 _files 内容复制到新前缀
        old_prefix = event_files_prefix_from_key(old_key)
        new_prefix = event_files_prefix(new_year, new_slug)
        if old_prefix != new_prefix:
            _copy_prefix(storage, old_prefix, new_prefix)
            storage.delete_prefix(old_prefix)

    # 更新索引
    idx.title = new_meta["title"]
    idx.start_at = new_meta["start"]
    idx.end_at = new_meta.get("end")
    idx.all_day = bool(new_meta.get("all_day", False))
    idx.status = new_meta.get("status", "planned")
    idx.tags_json = _dump_tags(new_meta.get("tags") or [])
    idx.color = new_meta.get("color")
    idx.source_url = new_meta.get("source_url")
    idx.file_path = target_key
    session.add(idx)
    session.commit()
    session.refresh(idx)
    return _build_event_out(target_key, new_meta, new_content)


def event_files_prefix_from_key(md_key: str) -> str:
    """从 events/<year>/<slug>.md 推出对应 _files/ 前缀。"""
    # events/2026/slug.md  →  events/2026/slug_files/
    p = md_key[:-3]  # 去掉 ".md"
    return f"{p}_files/"


def _copy_prefix(storage: Storage, src_prefix: str, dst_prefix: str) -> None:
    """把 src_prefix 下所有对象复制到 dst_prefix（key 前缀替换）。"""
    for old_key in list(storage.list_prefix(src_prefix)):
        new_key = dst_prefix + old_key[len(src_prefix) :]
        data = storage.get_bytes(old_key)
        storage.put_bytes(new_key, data)


def delete_event(session: Session, event_id: str) -> bool:
    storage = get_storage()
    idx = session.get(EventIndex, event_id)
    if not idx:
        return False
    md_key = event_md_key_from_index(idx)
    # 主份删除
    storage.delete(md_key)
    # 资产目录删除（按前缀）
    prefix = event_files_prefix_from_key(md_key)
    storage.delete_prefix(prefix)
    session.delete(idx)
    session.commit()
    return True


# 兼容旧 API：暴露 read_event / list_events / create_event / update_event / delete_event 名字
from sqlmodel import select  # noqa: E402  末尾 import，避免循环