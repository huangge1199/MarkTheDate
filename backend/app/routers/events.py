"""活动 CRUD API。"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlmodel import Session

from ..config import settings
from ..database import get_session
from ..models.event import EventIndex
from ..schemas.event import EventCreate, EventOut, EventSummary, EventUpdate
from ..services import file_manager

router = APIRouter(prefix="/api/events", tags=["events"])

# 单独 router 暴露事件资产文件，路径独立不与 event_id 冲突
files_router = APIRouter(prefix="/api/event-files", tags=["event-files"])


# ---- 抓取临时图片落地 ----

# fetch 接口把外链图下载到 storage（key = fetch/<sid>/<name>），并把正文里的 URL
# 改写为 /api/event-files/fetch/<sid>/<name>；前端保存事件时把 session_id 一并传回，
# 后端再把 fetch session 中的对象复制到 events/<year>/<slug>_files/，并把 URL
# 改写为 /api/event-files/events/<year>/<slug>_files/<name>。
_PREVIEW_URL_RE = re.compile(r"/api/event-files/fetch/(?P<sid>[A-Za-z0-9_-]+)/(?P<name>[\w.\-]+)")
# 整体匹配：![alt](/api/event-files/fetch/<sid>/<name>)
_IMG_PREVIEW_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(/api/event-files/fetch/(?P<sid>[A-Za-z0-9_-]+)/(?P<name>[\w.\-]+)\)"
)
_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)


def _slugify_local(text: str, max_len: int = 40) -> str:
    """把标题转成可作为目录名的 slug（保留中文）。"""
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return (s[:max_len] or "event")


def _materialise_content(
    content: str,
    session_id: str,
    *,
    event_id_for_dir: Optional[str] = None,
    slug: Optional[str] = None,
    start: Optional[datetime] = None,
) -> str:
    """把 markdown 里 /api/fetch/preview/<sid>/<name> 的图片引用替换为最终 /api/event-files/<key>，
    并把 fetch session 中的对象复制到 events/<year>/<slug>_files/，再删除原 fetch 对象。

    slug / start 至少需要其一，用来推算目标 _files/。
    """
    from ..services.storage import get_storage

    storage = get_storage()
    fetch_prefix = f"fetch/{session_id}/"

    # 先按 sid 探测 fetch/<sid>/ 下是否有对象；没有则直接清空 markdown 中的 preview 引用
    has_any = any(True for _ in storage.list_prefix(fetch_prefix))
    if not has_any:
        return _IMG_PREVIEW_RE.sub("", content)

    if slug is None and start is None:
        # 无目标信息：清空预览引用，并清理 fetch session
        storage.delete_prefix(fetch_prefix)
        return _IMG_PREVIEW_RE.sub("", content)

    year = start.year if start else datetime.now().year
    slug_norm = _slugify_local(slug or event_id_for_dir or "event")
    target_prefix = file_manager.event_files_prefix(year, slug_norm)

    seen: set[str] = set()

    def _rep(m: re.Match) -> str:
        sid = m.group("sid")
        name = m.group("name")
        alt = m.group("alt")
        if sid != session_id:
            return m.group(0)
        src_key = f"fetch/{sid}/{name}"
        if not storage.exists(src_key):
            return ""
        if name in seen:
            return f"![{alt or 'image'}](/api/event-files/{target_prefix}{name})"
        seen.add(name)
        dst_key = f"{target_prefix}{name}"
        try:
            data = storage.get_bytes(src_key)
            storage.put_bytes(dst_key, data)
            storage.delete(src_key)
        except Exception as e:
            logger.warning("copy {} -> {} failed: {}", src_key, dst_key, e)
            return ""
        return f"![{alt or 'image'}](/api/event-files/{target_prefix}{name})"

    new_content = _IMG_PREVIEW_RE.sub(_rep, content)

    # 删除 fetch session（剩余对象，包括 probe key 之外的）
    try:
        storage.delete_prefix(fetch_prefix)
    except Exception:
        pass

    return new_content


def _materialise_fetch_images(
    payload: EventCreate, session_id: str, title: str, start: datetime
) -> EventCreate:
    new_content = _materialise_content(
        payload.content or "",
        session_id,
        slug=title,
        start=start,
    )
    return payload.model_copy(update={"content": new_content})


def _summary(idx, session: Session) -> EventSummary:
    """从索引构造摘要。"""
    import json as _json

    tags = []
    try:
        tags = _json.loads(idx.tags_json) if idx.tags_json else []
    except Exception:
        pass
    return EventSummary(
        id=idx.id,
        title=idx.title,
        start=idx.start_at,
        end=idx.end_at,
        all_day=idx.all_day,
        status=idx.status,
        tags=tags,
        color=idx.color,
    )


@router.get("", response_model=List[EventSummary])
def list_events(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    session: Session = Depends(get_session),
):
    rows = file_manager.list_events(
        session,
        status=status,
        tag=tag,
        date_from=date_from,
        date_to=date_to,
    )
    return [_summary(r, session) for r in rows]


@router.post("", response_model=EventOut, status_code=201)
def create_event(
    payload: EventCreate,
    fetch_session_id: Optional[str] = Query(
        default=None,
        description="前端保存时把 fetch 接口返回的 session_id 一并传过来，"
        "后端会把临时图片搬到 events 目录。",
    ),
    session: Session = Depends(get_session),
):
    if fetch_session_id and payload.content:
        payload = _materialise_fetch_images(payload, fetch_session_id, payload.title, payload.start)
    return file_manager.create_event(session, payload)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, session: Session = Depends(get_session)):
    evt = file_manager.read_event(session, event_id)
    if not evt:
        raise HTTPException(404, "Event not found")
    return evt


@router.put("/{event_id}", response_model=EventOut)
def update_event(
    event_id: str,
    payload: EventUpdate,
    fetch_session_id: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    if fetch_session_id and payload.content:
        idx = session.get(EventIndex, event_id)
        if idx is not None:
            # 从索引的 file_path 推出当前 _files prefix，再把 fetch 中的图片复制过去
            md_key = file_manager.event_md_key_from_index(idx)
            target_prefix = file_manager.event_files_prefix_from_key(md_key)
            new_content = _IMG_PREVIEW_RE.sub(
                lambda m: _move_one_to_storage(m, fetch_session_id, target_prefix),
                payload.content,
            )
            # 清空整个 fetch session
            from ..services.storage import get_storage

            get_storage().delete_prefix(f"fetch/{fetch_session_id}/")
            payload = payload.model_copy(update={"content": new_content})
        else:
            new_content = _materialise_content(
                payload.content, fetch_session_id, event_id_for_dir=event_id
            )
            payload = payload.model_copy(update={"content": new_content})
    evt = file_manager.update_event(session, event_id, payload)
    if not evt:
        raise HTTPException(404, "Event not found")
    return evt


def _move_one_to_storage(m: re.Match, session_id: str, target_prefix: str) -> str:
    """把 fetch session 中的单张图片复制到目标 prefix，并返回替换后的 markdown。

    target_prefix 形如 'events/<year>/<slug>_files/'。
    """
    from ..services.storage import get_storage

    sid = m.group("sid")
    name = m.group("name")
    alt = m.group("alt")
    if sid != session_id:
        return m.group(0)
    storage = get_storage()
    src_key = f"fetch/{sid}/{name}"
    if not storage.exists(src_key):
        return ""
    dst_key = f"{target_prefix}{name}"
    try:
        data = storage.get_bytes(src_key)
        storage.put_bytes(dst_key, data)
        storage.delete(src_key)
    except Exception as e:
        logger.warning("copy {} -> {} failed: {}", src_key, dst_key, e)
        return ""
    return f"![{alt or 'image'}](/api/event-files/{target_prefix}{name})"


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: str, session: Session = Depends(get_session)):
    ok = file_manager.delete_event(session, event_id)
    if not ok:
        raise HTTPException(404, "Event not found")
    return None


@files_router.get("/{key:path}")
def serve_event_asset(key: str):
    """暴露对象存储里的对象给前端浏览器（markdown 渲染用）。

    支持两种 key 形式：
      - 新：events/<year>/<slug>_files/<filename>  或  fetch/<sid>/<filename>
      - 旧：<year>/<slug>/<filename>  （自动重写为 events/<year>/<slug>_files/<filename>）
    """
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise HTTPException(400, "invalid key")
    # 兼容旧 URL：<year>/<slug>/<filename>（3 段）→ events/<year>/<slug>_files/<filename>
    parts = key.split("/")
    if len(parts) == 3 and len(parts[0]) == 4 and parts[0].isdigit():
        year, slug, filename = parts
        if "/" not in slug and ".." not in slug and "/" not in filename:
            key = f"events/{year}/{slug}_files/{filename}"
    from ..services.storage import get_storage

    storage = get_storage()
    if not storage.exists(key):
        raise HTTPException(404, "not found")
    try:
        data = storage.get_bytes(key)
    except FileNotFoundError:
        raise HTTPException(404, "not found")

    # 简单 content-type 推断
    name = key.rsplit("/", 1)[-1]
    ct = _guess_content_type(name)
    from fastapi.responses import Response

    return Response(content=data, media_type=ct)


def _guess_content_type(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "bmp": "image/bmp",
        "md": "text/markdown; charset=utf-8",
    }.get(ext, "application/octet-stream")