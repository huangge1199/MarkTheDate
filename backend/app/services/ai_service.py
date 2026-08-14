"""AI 服务：OpenAI 兼容 / Ollama 可切换。"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from loguru import logger

from ..config import settings


def _resolve_provider() -> str:
    """读取最新 provider 设置（数据库 > 环境变量）。"""
    try:
        from ..database import engine
        from sqlmodel import Session, select
        from ..models.event import Setting

        with Session(engine) as s:
            row = s.exec(select(Setting).where(Setting.key == "ai_provider")).first()
            if row and row.value:
                return row.value
    except Exception:
        pass
    return settings.ai_provider


def _resolve(key: str, default: str) -> str:
    """从 settings 表读取最新值，缺失则回退到环境变量。"""
    try:
        from ..database import engine
        from sqlmodel import Session, select
        from ..models.event import Setting

        with Session(engine) as s:
            row = s.exec(select(Setting).where(Setting.key == key)).first()
            if row and row.value:
                return row.value
    except Exception:
        pass
    return default


async def _call_openai(system: str, user: str, *, json_mode: bool = True) -> str:
    """调用 OpenAI 兼容 API。"""
    from openai import AsyncOpenAI

    base_url = _resolve("ai_base_url", settings.ai_base_url)
    api_key = _resolve("ai_api_key", settings.ai_api_key) or "sk-no-key"
    model = _resolve("ai_model", settings.ai_model)

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def _call_ollama(system: str, user: str, *, json_mode: bool = True) -> str:
    """调用本地 Ollama。"""
    import ollama

    base_url = _resolve("ollama_base_url", settings.ollama_base_url)
    model = _resolve("ollama_model", settings.ollama_model)
    client = ollama.AsyncClient(host=base_url)
    fmt = "json" if json_mode else ""
    resp = await client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format=fmt,
    )
    return resp["message"]["content"] or ""


async def chat(system: str, user: str, *, json_mode: bool = True) -> str:
    """根据 provider 分发调用。"""
    provider = _resolve_provider()
    logger.debug("AI call via {}", provider)
    if provider == "ollama":
        return await _call_ollama(system, user, json_mode=json_mode)
    return await _call_openai(system, user, json_mode=json_mode)


async def extract_event_from_text(
    *, title: str, description: str, text: str, url: str
) -> Dict[str, Any]:
    """从网页文本提取活动元数据 + Markdown 描述。"""
    system = (
        "你是一个活动信息提取助手。根据用户提供的网页内容，提取活动信息并以 JSON 输出。"
        'JSON 结构: {"title": str, "start": ISO8601 or null, "end": ISO8601 or null,'
        ' "tags": [str], "content": Markdown 格式描述}'
    )
    user = f"""标题: {title}
URL: {url}
描述: {description}
正文:
{text[:3000]}

请严格输出 JSON，不要包含解释。"""
    raw = await chat(system, user, json_mode=True)
    try:
        return json.loads(raw)
    except Exception:
        # 尝试剥离 markdown 代码块
        if "```" in raw:
            raw = raw.split("```", 2)[1] if "```" in raw else raw
            raw = raw.replace("json", "", 1).strip()
        return json.loads(raw)


async def optimize_markdown(content: str, instruction: Optional[str] = None) -> Dict[str, Any]:
    """优化 Markdown 正文。"""
    extra = f"\n附加要求: {instruction}" if instruction else ""
    system = (
        "你是 Markdown 编辑助手。改进用户提供的 Markdown 文档：修正语法、改善结构、"
        "补充合理的标题与列表。保持原意，不要杜撰内容。"
        '输出 JSON: {"optimized": str, "summary": str 简要说明改了什么}'
    )
    user = f"{content}\n{extra}"
    raw = await chat(system, user, json_mode=True)
    try:
        return json.loads(raw)
    except Exception:
        if "```" in raw:
            raw = raw.split("```", 2)[1]
            raw = raw.replace("json", "", 1).strip()
        return json.loads(raw)


async def suggest_metadata(content: str) -> Dict[str, Any]:
    """从正文提取建议元数据。"""
    system = (
        "你是活动元数据提取助手。根据 Markdown 正文提取活动信息。"
        '输出 JSON: {"title": str or null, "start": ISO8601 or null,'
        ' "end": ISO8601 or null, "tags": [str], "summary": str}'
    )
    user = content[:4000]
    raw = await chat(system, user, json_mode=True)
    try:
        return json.loads(raw)
    except Exception:
        return {}