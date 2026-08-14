"""工具方法。"""
from datetime import datetime, timezone


def to_aware(dt: datetime) -> datetime:
    """确保 datetime 带时区（若 naive，按本地时区附加）。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt