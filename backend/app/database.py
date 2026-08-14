"""SQLite 数据库初始化与会话。"""
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

# SQLite 需要 check_same_thread=False 以便在 FastAPI 多线程中使用
engine = create_engine(
    f"sqlite:///{settings.db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """创建所有表。"""
    # 导入模型以触发元数据注册
    from .models import event  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """FastAPI 依赖：获取数据库会话。"""
    with Session(engine) as session:
        yield session