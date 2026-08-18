"""URL 抓取 API。"""
from __future__ import annotations

import hashlib
import re
import secrets
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from selectolax.parser import HTMLParser
from loguru import logger

from ..config import settings

from ..schemas.ai import FetchRequest, FetchResponse


router = APIRouter(prefix="/api/fetch", tags=["fetch"])


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MarkTheDateBot/1.0"


def _attr(parser: HTMLParser, *names) -> Optional[str]:
    """从 CSS 选择器里读 content/value 属性。"""
    for sel in names:
        node = parser.css_first(sel)
        if node:
            v = node.attributes.get("content") or node.attributes.get("value")
            if v:
                return v.strip()
    return None


def _js_var(html: str, *names: str) -> Optional[str]:
    """从内联 JS 中抓取 var/let/const/window 变量字符串值。

    形如: var msg_title = "...";  /  window.msg_title = '...';
    """
    for name in names:
        pattern = (
            rf'(?:window\.)?(?:var|let|const)?\s*{re.escape(name)}\s*=\s*'
            rf'["\']([^"\']+)["\']'
        )
        m = re.search(pattern, html)
        if m:
            return m.group(1).strip()
    return None


def _parse_meta(html: str) -> dict:
    """解析 HTML：OG / meta / 微信内置 JS 变量（msg_title 等）。"""
    parser = HTMLParser(html)
    out: dict = {}

    # 1) 标题：og / twitter / <title> / 微信 msg_title
    out["title"] = (
        _attr(
            parser,
            'meta[property="og:title"]',
            'meta[name="twitter:title"]',
            'meta[name="title"]',
        )
        or _js_var(html, "msg_title", "title")
        or _attr(parser, "title")
    )

    out["description"] = _attr(
        parser,
        'meta[property="og:description"]',
        'meta[name="twitter:description"]',
        'meta[name="description"]',
    ) or _js_var(html, "msg_desc", "msg_description", "description")

    out["site_name"] = _attr(parser, 'meta[property="og:site_name"]')
    out["image"] = _attr(parser, 'meta[property="og:image"]')

    # 2) 时间：meta / 微信 create_time / publish_time（秒级时间戳）
    time_str = _attr(
        parser,
        'meta[property="article:published_time"]',
        'meta[property="og:article:published_time"]',
        'meta[itemprop="datePublished"]',
        'meta[name="pubdate"]',
        'meta[name="publishdate"]',
        'meta[name="date"]',
    )
    ts_raw = _js_var(html, "publish_time", "create_time", "update_time")
    out["time_str"] = time_str
    out["time_ts"] = ts_raw

    # 3) 正文：优先 #js_content（微信公众号），其次 article/main/body
    body = (
        parser.css_first("#js_content")
        or parser.css_first(".rich_media_content")
        or parser.css_first("article")
        or parser.css_first("main")
        or parser.body
    )
    if body:
        out["text"] = _html_to_markdown(body.html)[:4000]
    else:
        out["text"] = ""
    return out


# 自闭合元素（含常见变体）
_VOID_TAG_RE = re.compile(
    r"<\s*(?:br|hr|img|input|meta|link)\b[^>]*>", re.I
)
# 图片：保留为 Markdown 图片（缺 alt 时用空串）
_IMG_RE = re.compile(
    r'<\s*img\b([^>]*)>', re.I
)
# <a ... href="...">text</a>
_A_RE = re.compile(
    r'<\s*a\b[^>]*?\bhref\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</\s*a\s*>',
    re.I | re.S,
)
# 段落 / 标题 / 列表项 → 临时占位（再统一换成 \n）
_P_OPEN_CLOSE = re.compile(
    r"<\s*(p|/p|h[1-6]|/h[1-6]|li|/li|ul|/ul|ol|/ol|blockquote|/blockquote|section|/section)\b[^>]*>",
    re.I,
)
# 其它标签 → 删
_OTHER_TAG_RE = re.compile(r"<\/?[a-zA-Z][^>]*>", re.S)


def _md_attr(attrs: str, name: str) -> Optional[str]:
    m = re.search(rf'\b{name}\s*=\s*["\']([^"\']*)["\']', attrs, re.I)
    return m.group(1) if m else None


def _html_to_markdown(html: str) -> str:
    """把正文 HTML 转换成带段落结构的轻量 Markdown。

    处理顺序：
      1) 删掉 <script> / <style>
      2) 把 <br> 换成换行
      3) <img> → ![alt](src)
      4) <a href>text</a> → [text](href)
      5) <p>/<h1-6>/<li>/<ul>/<ol>/<blockquote>/<section> → 临时占位符
      6) 删掉剩余标签
      7) 占位符 → 真实换行
      8) 多余空行合并
    """
    if not html:
        return ""

    # 1) 删 script/style
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)

    # 2) <br> / <hr> → 换行
    html = re.sub(r"<\s*br\s*/?\s*>", "\n", html, flags=re.I)
    html = re.sub(r"<\s*hr\s*/?\s*>", "\n\n---\n\n", html, flags=re.I)

    # 3) <img> → Markdown 图片
    def _img_sub(m: re.Match) -> str:
        attrs = m.group(1)
        src = _md_attr(attrs, "data-src") or _md_attr(attrs, "src") or ""
        alt = _md_attr(attrs, "alt") or ""
        return f"\n\n![{alt}]({src})\n\n" if src else ""

    html = _IMG_RE.sub(_img_sub, html)

    # 4) <a href>text</a> → [text](href)
    def _a_sub(m: re.Match) -> str:
        href, inner = m.group(1), m.group(2)
        inner = _OTHER_TAG_RE.sub("", inner)
        inner = re.sub(r"\s+", " ", inner).strip()
        return f"[{inner or href}]({href})"

    html = _A_RE.sub(_a_sub, html)

    # 5) 段落/标题/列表项开闭合 → 临时占位
    html = _P_OPEN_CLOSE.sub(lambda m: "\n\n§§§\n\n", html)

    # 6) 剩余标签全部删
    html = _OTHER_TAG_RE.sub("", html)

    # 7) 占位符 → 真实换行，并把列表项渲染成 "- "
    # 先把"占位符单独成行"的情况归一
    lines = html.split("\n")
    out_lines: list[str] = []
    in_list = False
    for ln in lines:
        stripped = ln.strip()
        if stripped == "§§§":
            out_lines.append("")
            in_list = False
            continue
        if stripped:
            # 如果上一行是空且没识别出 ul/ol（占位符已统一为 §§§），仍按段落处理
            out_lines.append(stripped)
            in_list = False
        else:
            out_lines.append("")
            in_list = False

    text = "\n".join(out_lines)

    # 8) 合并多余空行 / 去首尾空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_time(time_str: Optional[str]) -> Optional[datetime]:
    """尝试解析时间字符串或纯数字时间戳。"""
    if not time_str:
        return None
    s = time_str.strip()
    # 纯整数 / 纯小数 → 当作秒级时间戳（兼容微信 create_time）
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        try:
            return datetime.fromtimestamp(float(s), tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    from dateutil import parser as dateparser  # type: ignore

    try:
        return dateparser.parse(s)
    except Exception:
        return None


_CN_DATE = r"\d{4}年\d{1,2}月\d{1,2}日"
_CN_DATE_NO_YEAR = r"\d{1,2}月\d{1,2}日"
_RANGE_SEP = r"(?:至|到|—|–|-|~|～|—)"
_RANGE_RE = re.compile(
    rf"({_CN_DATE})\s*{_RANGE_SEP}\s*({_CN_DATE}|{_CN_DATE_NO_YEAR})"
)


def _extract_event_range(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """从正文里解析中文日期区间（如"2026年8月1日至10月31日"）。

    仅当两端都能解析成 datetime 时返回，否则返回 (None, None)。
    支持的写法：
      - 2026年8月1日至10月31日   （短端省略年份，自动继承起始端年份）
      - 2026年8月1日—2026年10月31日
      - 2026年8月1日 ~ 2026年10月31日
    """
    if not text:
        return None, None
    m = _RANGE_RE.search(text)
    if not m:
        return None, None
    start_raw, end_raw = m.group(1), m.group(2)
    from dateutil import parser as dateparser  # type: ignore

    try:
        start = dateparser.parse(start_raw, fuzzy=True)
    except Exception:
        return None, None
    try:
        end = dateparser.parse(end_raw, fuzzy=True)
    except Exception:
        return None, None
    if start is None or end is None:
        return None, None
    # 短端省略年份时，dateutil 会默认当前年，需要补上起端的年份
    if "年" not in end_raw and start.year:
        try:
            end = end.replace(year=start.year)
        except ValueError:
            return None, None
    return start, end


# ---- 图片下载与临时目录管理 -----------------------------------------------

_IMG_MD_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


def _session_dir(session_id: str) -> Path:
    """返回 session 临时目录（绝对路径）。"""
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(400, "invalid session_id")
    d = settings.fetch_tmp_dir / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ext_from_url(url: str, default: str = ".jpg") -> str:
    """从 URL 推断文件扩展名，缺省 .jpg。"""
    p = url.split("?", 1)[0]
    if "." in p.rsplit("/", 1)[-1]:
        ext = "." + p.rsplit(".", 1)[-1].lower()
        if len(ext) <= 6 and re.fullmatch(r"\.[a-z0-9]+", ext):
            return ext
    return default


async def _download_images(markdown: str, session_id: str) -> str:
    """把 markdown 里所有外链图片下载并 put 到 storage（key = fetch/<session_id>/<filename>），
    返回改写后的 markdown，URL 形如 /api/event-files/fetch/<session_id>/<filename>。
    重复 URL 共享同一文件名。
    """
    from ..services.storage import get_storage

    urls = [m.group("url") for m in _IMG_MD_RE.finditer(markdown)]
    if not urls:
        return markdown

    # 去重 + 准备映射
    unique_urls = list(dict.fromkeys(urls))
    mapping: dict[str, str] = {}
    storage = get_storage()

    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": UA, "Referer": "https://mp.weixin.qq.com/"},
    ) as client:
        for url in unique_urls:
            try:
                r = await client.get(url)
                r.raise_for_status()
                data = r.content
            except Exception as e:
                logger.warning("Skip image ({}): {}", e.__class__.__name__, url)
                continue
            if len(data) > 10 * 1024 * 1024:
                logger.warning("Skip too-large image ({} bytes): {}", len(data), url)
                continue
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
            ext = _ext_from_url(url)
            name = f"{digest}{ext}"
            key = f"fetch/{session_id}/{name}"
            content_type = r.headers.get("content-type")
            storage.put_bytes(key, data, content_type=content_type)
            mapping[url] = name

    if not mapping:
        return markdown

    def _rep(m: re.Match) -> str:
        url = m.group("url")
        name = mapping.get(url)
        if not name:
            return m.group(0)
        return f"![image](/api/event-files/fetch/{session_id}/{name})"

    return _IMG_MD_RE.sub(_rep, markdown)


@router.post("", response_model=FetchResponse)
async def fetch_url(payload: FetchRequest):
    """从 URL 抓取活动草稿。

    1) 解析 OG / meta 标签 + 微信 JS 变量
    2) 关键字段缺失时调用 LLM 兜底
    """
    url = str(payload.url)
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={"User-Agent": UA}) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        logger.exception("Fetch failed: {}", e)
        raise HTTPException(502, f"Failed to fetch URL: {e}")

    meta = _parse_meta(html)
    title = meta.get("title") or ""
    description = meta.get("description") or ""
    text = meta.get("text") or ""

    # 1) 正文里若有明确活动日期区间（如"展览时间：2026年8月1日至10月31日"），
    #    优先采用它作为活动的起止时间；这比 create_time（公众号发布时间）更准确。
    event_start, event_end = _extract_event_range(text)

    # 2) 否则退回文章发布时间
    fallback_start = _parse_time(meta.get("time_str")) or _parse_time(meta.get("time_ts"))

    start = event_start or fallback_start
    end: Optional[datetime] = event_end

    confidence = "high" if title and start else "medium"
    tags: list[str] = []
    content_ai: Optional[str] = None

    # 若关键字段缺失，调用 AI 兜底
    if not title or not start or len(text) < 50:
        from ..services import ai_service

        try:
            ai_data = await ai_service.extract_event_from_text(
                title=title or url,
                description=description,
                text=text or description,
                url=url,
            )
            title = title or ai_data.get("title") or url
            start = start or (ai_data.get("start") if isinstance(ai_data.get("start"), datetime) else _parse_time(ai_data.get("start")))
            if end is None:
                end_raw = ai_data.get("end")
                end = end_raw if isinstance(end_raw, datetime) else _parse_time(end_raw)
            tags = ai_data.get("tags") or []
            content_ai = ai_data.get("content") or description or text[:800]
            confidence = "high"
        except Exception as e:
            logger.warning("AI fallback failed: {}", e)
            content_ai = description or text[:800]

    if content_ai is None:
        content_ai = description or text[:800]

    # 把正文里的外链图片下载到对象存储（key = fetch/<session_id>/<filename>），
    # 并改写 markdown 为临时 URL。前端保存事件时把 session_id 一并传回，后端再把
    # 图片复制到 events/<year>/<slug>_files/。
    session_id = secrets.token_urlsafe(12)
    try:
        content_with_local_images = await _download_images(content_ai, session_id)
    except Exception as e:
        logger.warning("Image download failed: {}", e)
        content_with_local_images = content_ai

    return FetchResponse(
        title=title or url,
        start=start,
        end=end,
        all_day=False,
        tags=tags,
        source_url=url,
        content=content_with_local_images,
        raw_html_excerpt=text[:600],
        confidence=confidence,  # type: ignore
        session_id=session_id,
    )


@router.get("/preview/{session_id}/{filename}")
def preview_image(session_id: str, filename: str):
    """返回抓取会话中的临时图片，供前端预览。

    实际存储在对象存储（key = fetch/<session_id>/<filename>），由后端代理流回。
    推荐直接访问 /api/event-files/fetch/<session_id>/<filename>（files_router 暴露），
    这里保留是为了向后兼容旧前端代码。
    """
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(400, "invalid session_id")
    if not re.fullmatch(r"[\w.\-]+", filename) or "/" in filename or "\\" in filename:
        raise HTTPException(400, "invalid filename")
    from ..services.storage import get_storage

    storage = get_storage()
    key = f"fetch/{session_id}/{filename}"
    if not storage.exists(key):
        raise HTTPException(404, "not found")
    try:
        data = storage.get_bytes(key)
    except FileNotFoundError:
        raise HTTPException(404, "not found")
    # 用合适的 content-type
    ct = _guess_content_type(filename)
    return Response(content=data, media_type=ct)


@router.delete("/preview/{session_id}")
def discard_preview(session_id: str):
    """删除指定抓取会话的所有临时对象（在对象存储上按 prefix 删）。"""
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(400, "invalid session_id")
    from ..services.storage import get_storage

    storage = get_storage()
    try:
        n = storage.delete_prefix(f"fetch/{session_id}/")
        return {"ok": True, "removed": n}
    except Exception as e:
        logger.warning("Failed to remove fetch session {}: {}", session_id, e)
        raise HTTPException(500, f"remove failed: {e}")


def cleanup_stale_sessions(max_age_seconds: int = 3600) -> int:
    """清理超过 max_age_seconds 未访问的临时 session 对象。

    S3 没有 mtime 概念；这里通过最近一次 list 来推断（若 bucket 内对象总数稳定，
    仅 delete prefix）。返回删除的 session 数（不一定准确）。
    """
    from ..services.storage import get_storage

    storage = get_storage()
    # S3 后端：通过 list + head_object 的 LastModified 判断；local 后端：直接看 mtime
    if storage.backend_name() == "local":
        base = settings.fetch_tmp_dir
        if not base.exists():
            return 0
        now = time.time()
        removed = 0
        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            try:
                mtime = entry.stat().st_mtime
            except FileNotFoundError:
                continue
            if now - mtime > max_age_seconds:
                try:
                    from ..services.fs_ops import remove_path

                    remove_path(entry)
                    removed += 1
                except Exception as e:
                    logger.warning("Failed to remove stale {}: {}", entry, e)
        if removed:
            logger.info("Cleaned {} stale fetch session(s)", removed)
        return removed

    # S3 后端：list fetch/ 下对象，对每个 session 的首个对象取 LastModified
    try:
        sessions = set()
        for key in storage.list_prefix("fetch/"):
            # key 形如 "fetch/<session>/<filename>"
            parts = key.split("/", 2)
            if len(parts) >= 2:
                sessions.add(parts[1])
        if not sessions:
            return 0
        # 对每个 session：head 第一个对象看 LastModified
        now = time.time()
        from datetime import datetime, timezone

        from ..config import settings as _s

        # 用本地通用 client 的 head_object
        import boto3  # type: ignore
        from botocore.client import Config as BotoConfig  # type: ignore

        client = boto3.client(
            "s3",
            endpoint_url=_s.s3_endpoint_url or None,
            aws_access_key_id=_s.s3_access_key,
            aws_secret_access_key=_s.s3_secret_key,
            region_name=_s.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )
        removed = 0
        for sid in sessions:
            prefix = f"fetch/{sid}/"
            for key in list(storage.list_prefix(prefix)):
                try:
                    h = client.head_object(Bucket=_s.s3_bucket, Key=key)
                    lm = h.get("LastModified")
                    if lm is None or (now - lm.replace(tzinfo=timezone.utc).timestamp()) > max_age_seconds:
                        storage.delete_prefix(prefix)
                        removed += 1
                except Exception as e:
                    logger.warning("head {} failed: {}", key, e)
                break  # 只检查首个
        if removed:
            logger.info("Cleaned {} stale fetch session(s)", removed)
        return removed
    except Exception as e:
        logger.warning("cleanup_stale_sessions failed: {}", e)
        return 0


def _guess_content_type(filename: str) -> str:
    """根据扩展名猜测 content-type。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "bmp": "image/bmp",
    }.get(ext, "application/octet-stream")