"""文件/目录操作工具。

集中处理 Windows 联接（junction）的安全删除，避免散落的 shutil.rmtree /
Path.unlink 调用导致：
- 目录型 junction 用 rmdir 才能删，文件型 junction 必须用 del /F /Q；
- Path.is_file / is_dir 对 junction 会跟随到目标，类型判断不可靠；
- 中文路径在 subprocess 调用时需用短路径规避编码问题。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from loguru import logger


def _junction_remove(link: Path) -> None:
    """删除目录/文件联接（junction），不跟随到目标。

    路径里如果包含 unicode（如中文），先用短路径回避编码问题；
    目录型用 rmdir，文件型 fallback 到 del /F /Q。
    """
    if not link.is_junction() and not link.exists():
        return
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(512)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(link), buf, 512)
        target = buf.value if n > 0 else str(link)
    except Exception:
        target = str(link)
    r1 = subprocess.run(["cmd", "/c", "rmdir", target], capture_output=True, text=True)
    if r1.returncode != 0:
        r2 = subprocess.run(["cmd", "/c", "del", "/F", "/Q", target], capture_output=True, text=True)
        if r2.returncode != 0:
            logger.warning("junction_remove failed: {} (rmdir: {}, del: {})", link, r1.stderr, r2.stderr)


def remove_path(path: Path) -> None:
    """统一删除入口：兼容普通文件、目录、文件型 junction、目录型 junction。

    任意类型都安全删除，不跟随 junction 到目标。
    """
    if not path.is_junction() and not path.exists():
        return
    if path.is_junction():
        _junction_remove(path)
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass