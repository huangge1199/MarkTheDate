"""AI 接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..database import get_session
from ..schemas.ai import AIOptimizeRequest, AIOptimizeResponse, AISuggestRequest, AISuggestResponse
from ..services import ai_service, file_manager


router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/optimize", response_model=AIOptimizeResponse)
async def optimize_markdown(payload: AIOptimizeRequest, session: Session = Depends(get_session)):
    """根据 event_id 优化 Markdown，返回 before/after 用于 diff。"""
    read = file_manager.read_event_content(payload.event_id, session)
    if not read:
        raise HTTPException(404, "Event not found")
    content, _ = read

    try:
        result = await ai_service.optimize_markdown(content, payload.instruction)
    except Exception as e:
        raise HTTPException(500, f"AI optimize failed: {e}")

    after = result.get("optimized") or content
    return AIOptimizeResponse(
        event_id=payload.event_id,
        before=content,
        after=after,
        diff_summary=result.get("summary"),
    )


@router.post("/apply/{event_id}")
async def apply_optimized(event_id: str, body: dict, session: Session = Depends(get_session)):
    """应用优化后的正文到 .md 文件。"""
    new_content = body.get("content")
    if not isinstance(new_content, str):
        raise HTTPException(400, "content required")
    fp = file_manager.write_event_content(event_id, session, new_content)
    if not fp:
        raise HTTPException(404, "Event not found")
    return {"ok": True, "file_path": fp}


@router.post("/suggest", response_model=AISuggestResponse)
async def suggest_metadata(payload: AISuggestRequest):
    """从正文提取元数据建议。"""
    try:
        result = await ai_service.suggest_metadata(payload.content)
    except Exception as e:
        raise HTTPException(500, f"AI suggest failed: {e}")
    return AISuggestResponse(**result)