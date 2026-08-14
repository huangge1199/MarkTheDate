"""URL 抓取 API。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from selectolax.parser import HTMLParser
from loguru import logger

from ..schemas.ai import FetchRequest, FetchResponse


router = APIRouter(prefix="/api/fetch", tags=["fetch"])


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MarkTheDateBot/1.0"


def _parse_meta(html: str) -> dict:
    """解析 HTML 中的 OG / meta 标签。"""
    parser = HTMLParser(html)
    out: dict = {}

    def _attr(*names) -> Optional[str]:
        for sel in names:
            node = parser.css_first(sel)
            if node:
                v = node.attributes.get("content") or node.attributes.get("value")
                if v:
                    return v.strip()
        return None

    out["title"] = _attr(
        'meta[property="og:title"]',
        'meta[name="twitter:title"]',
        'meta[name="title"]',
        "title",
    )
    out["description"] = _attr(
        'meta[property="og:description"]',
        'meta[name="twitter:description"]',
        'meta[name="description"]',
    )
    out["site_name"] = _attr('meta[property="og:site_name"]')
    out["image"] = _attr('meta[property="og:image"]')

    # 时间
    time_str = _attr(
        'meta[property="article:published_time"]',
        'meta[property="og:article:published_time"]',
        'meta[itemprop="datePublished"]',
        'meta[name="pubdate"]',
        'meta[name="publishdate"]',
        'meta[name="date"]',
    )
    out["time_str"] = time_str

    # 提取正文（粗略）
    body = parser.css_first("article") or parser.css_first("main") or parser.body
    out["text"] = body.text(strip=True)[:4000] if body else ""
    return out


def _parse_time(time_str: Optional[str]) -> Optional[datetime]:
    """尝试解析时间字符串。"""
    if not time_str:
        return None
    from dateutil import parser as dateparser  # type: ignore

    try:
        return dateparser.parse(time_str)
    except Exception:
        return None


@router.post("", response_model=FetchResponse)
async def fetch_url(payload: FetchRequest):
    """从 URL 抓取活动草稿。

    1) 解析 OG / meta 标签
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
    start = _parse_time(meta.get("time_str"))

    confidence = "high" if title and start else "medium"

    # 若关键字段缺失，调用 AI 兜底
    if not title or not start or len(text) < 50:
        from ..services import ai_service

        tags: list[str] = []
        try:
            ai_data = await ai_service.extract_event_from_text(
                title=title or url,
                description=description,
                text=text or description,
                url=url,
            )
            title = title or ai_data.get("title") or url
            start = start or (ai_data.get("start") if isinstance(ai_data.get("start"), datetime) else _parse_time(ai_data.get("start")))
            end_raw = ai_data.get("end")
            end = end_raw if isinstance(end_raw, datetime) else _parse_time(end_raw)
            tags = ai_data.get("tags") or []
            content_ai = ai_data.get("content") or description or text[:800]
            confidence = "high"
        except Exception as e:
            logger.warning("AI fallback failed: {}", e)
            content_ai = description or text[:800]
    else:
        tags = []
        content_ai = description or text[:800]

    return FetchResponse(
        title=title or url,
        start=start,
        end=end if 'end' in locals() else None,
        all_day=False,
        tags=tags,
        source_url=url,
        content=content_ai,
        raw_html_excerpt=text[:600],
        confidence=confidence,  # type: ignore
    )