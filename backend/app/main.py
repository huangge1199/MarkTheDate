"""FastAPI 应用入口。"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import settings
from .database import init_db
from .routers import ai, calendar, events, fetch, notify, settings as settings_router
from .services import notifier


scheduler = AsyncIOScheduler()


async def _email_scan_job():
    """定时任务：扫描邮件提醒。"""
    try:
        n = await notifier.scan_pending_emails()
        logger.info("Email scan: sent={}", n)
    except Exception as e:
        logger.exception("Email scan error: {}", e)


def _tmp_cleanup_job():
    """定时任务：清理超过 1 小时的抓取临时 session。"""
    try:
        fetch.cleanup_stale_sessions(max_age_seconds=3600)
    except Exception as e:
        logger.exception("tmp cleanup error: {}", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 启动调度器
    scheduler.add_job(
        _email_scan_job,
        IntervalTrigger(minutes=1),
        id="email_scan",
        replace_existing=True,
    )
    scheduler.add_job(
        _tmp_cleanup_job,
        IntervalTrigger(minutes=10),
        id="tmp_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("MarkTheDate backend started on {}:{}", settings.host, settings.port)
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="MarkTheDate API",
    version="0.1.0",
    description="活动日期管理 API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],  # 部署时收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"app": "MarkTheDate", "version": "0.1.0", "docs": "/docs"}


app.include_router(events.router)
app.include_router(events.files_router)
app.include_router(calendar.router)
app.include_router(fetch.router)
app.include_router(ai.router)
app.include_router(notify.router)
app.include_router(settings_router.router)