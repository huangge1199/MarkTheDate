"""对象存储抽象层。

提供统一的 `Storage` 接口，屏蔽本地文件系统和 S3 兼容对象存储（rustfs / MinIO / AWS S3）的差异。
所有上层代码（file_manager、routers）只通过这个接口读写资源。

Key 命名约定：
  - markdown:  events/<year>/<slug>.md
  - asset:     events/<year>/<slug>_files/<filename>
  - 跨年活动只放 start 年份的主份；end 及中间年份不建 entry（按需读主份即可）
"""
from __future__ import annotations

import io
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Iterable, Optional, Tuple

from loguru import logger

from ..config import settings


class Storage(ABC):
    """抽象存储接口。"""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> None:
        """把字节流写入指定 key。覆盖已有对象。"""

    @abstractmethod
    def put_file(self, key: str, src_path: Path, content_type: Optional[str] = None) -> None:
        """把本地文件写入指定 key。"""

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """读取对象的字节内容。不存在时抛 FileNotFoundError。"""

    @abstractmethod
    def open_read(self, key: str) -> BinaryIO:
        """以二进制读模式打开对象；返回 context-manager-friendly 的 stream。"""

    @abstractmethod
    def delete(self, key: str) -> None:
        """删除单个对象；不存在不报错。"""

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """删除以 prefix 开头的所有对象；返回删除数量。"""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """对象是否存在。"""

    @abstractmethod
    def list_prefix(self, prefix: str) -> Iterable[str]:
        """返回 prefix 下的所有对象 key。"""

    @abstractmethod
    def public_url(self, key: str) -> str:
        """返回一个可在浏览器中直接访问该对象的 URL（GET）。

        本地存储返回后端 API 路径（前端经 vite proxy 转发）；
        S3 存储返回配置的 public base URL（如有）或预签名 URL。
        """

    @abstractmethod
    def backend_name(self) -> str:
        """返回后端实现名（"local" / "s3"）。用于诊断日志。"""


# ----------------------------------------------------------------------
# 本地文件系统实现
# ----------------------------------------------------------------------


class LocalStorage(Storage):
    """把对象存到本地 data/ 目录下。适合开发或单机部署。"""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, key: str) -> Path:
        # key 形如 "events/2026/slug.md"，禁止越权访问（防止 ..）
        if ".." in key.split("/") or key.startswith("/"):
            raise ValueError(f"invalid key: {key!r}")
        return self._root / key

    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> None:
        p = self._resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def put_file(self, key: str, src_path: Path, content_type: Optional[str] = None) -> None:
        p = self._resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(p))

    def get_bytes(self, key: str) -> bytes:
        p = self._resolve(key)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(key)
        return p.read_bytes()

    def open_read(self, key: str) -> BinaryIO:
        p = self._resolve(key)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(key)
        return p.open("rb")

    def delete(self, key: str) -> None:
        p = self._resolve(key)
        if not p.exists():
            return
        # 普通文件 / 目录 / junction 都交给 fs_ops 处理
        from .fs_ops import remove_path

        remove_path(p)

    def delete_prefix(self, prefix: str) -> int:
        base = self._resolve(prefix)
        if not base.exists():
            return 0
        n = 0
        for p in base.rglob("*"):
            try:
                if p.is_file() or p.is_junction():
                    from .fs_ops import remove_path

                    remove_path(p)
                    n += 1
            except Exception:
                continue
        # 删除空目录（自下而上）
        for p in sorted(base.rglob("*"), reverse=True):
            if p.is_dir() and not any(p.iterdir()):
                try:
                    p.rmdir()
                except OSError:
                    pass
        try:
            if base.is_dir() and not any(base.iterdir()):
                base.rmdir()
        except OSError:
            pass
        return n

    def exists(self, key: str) -> bool:
        p = self._resolve(key)
        return p.exists()

    def list_prefix(self, prefix: str) -> Iterable[str]:
        base = self._resolve(prefix)
        if not base.exists():
            return []
        out: list[str] = []
        for p in base.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self._root).as_posix()
                out.append(rel)
        return out

    def public_url(self, key: str) -> str:
        # 本地存储用后端 API 路径暴露，前端经 vite proxy 转发
        return f"/api/event-files/{key}"

    def backend_name(self) -> str:
        return "local"


# ----------------------------------------------------------------------
# S3 兼容对象存储实现（rustfs / MinIO / AWS S3）
# ----------------------------------------------------------------------


class S3Storage(Storage):
    """S3 兼容对象存储实现。

    通过 boto3 同步客户端操作；适用于 rustfs、MinIO、AWS S3、阿里云 OSS、
    腾讯云 COS 等所有支持 S3 API 的存储。
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        path_style: bool = True,
        public_base_url: Optional[str] = None,
        presign_expires: int = 3600,
    ) -> None:
        try:
            import boto3
            from botocore.client import Config as BotoConfig  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "S3Storage requires boto3 + botocore; install via requirements.txt"
            ) from e
        self._bucket = bucket
        self._public_base_url = (public_base_url or "").rstrip("/")
        self._presign_expires = presign_expires
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if path_style else "virtual"},
                connect_timeout=10,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        # 启动时校验一次 bucket 可达性（不抛错时仍可继续，懒失败）
        try:
            self._client.head_bucket(Bucket=bucket)
        except Exception as e:
            logger.warning("S3Storage head_bucket failed (will retry on demand): {}", e)

    # --- key 校验 ---
    @staticmethod
    def _check_key(key: str) -> None:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise ValueError(f"invalid key: {key!r}")

    # --- 写入 ---
    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> None:
        self._check_key(key)
        kwargs: dict = {"Bucket": self._bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        self._client.put_object(**kwargs)

    def put_file(self, key: str, src_path: Path, content_type: Optional[str] = None) -> None:
        self._check_key(key)
        kwargs: dict = {"Bucket": self._bucket, "Key": key, "Filename": str(src_path)}
        # boto3 也支持 Fileobj，这里用 Filename 走 SDK 内部的多分片优化
        if content_type:
            kwargs["ExtraArgs"] = {"ContentType": content_type}
        self._client.upload_file(**kwargs)
        # 上传成功，删除本地源（boto3 不会自动删）
        try:
            src_path.unlink()
        except FileNotFoundError:
            pass

    # --- 读取 ---
    def get_bytes(self, key: str) -> bytes:
        self._check_key(key)
        try:
            r = self._client.get_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey:
            raise FileNotFoundError(key)
        except Exception as e:
            # boto3 通用 ClientError; 用错误码区分
            try:
                from botocore.exceptions import ClientError  # type: ignore

                if isinstance(e, ClientError) and e.response.get("Error", {}).get("Code") in (
                    "NoSuchKey",
                    "404",
                ):
                    raise FileNotFoundError(key) from e
            except ImportError:
                pass
            raise
        body = r["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def open_read(self, key: str) -> BinaryIO:
        # 把字节读到 BytesIO 再返回（避免每个调用方管理 body.close）
        data = self.get_bytes(key)
        return io.BytesIO(data)

    # --- 删除 ---
    def delete(self, key: str) -> None:
        self._check_key(key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as e:
            logger.warning("S3 delete failed for {}: {}", key, e)

    def delete_prefix(self, prefix: str) -> int:
        self._check_key(prefix)
        n = 0
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            objs = page.get("Contents", [])
            if not objs:
                continue
            # 一次最多 1000 个，可分批
            keys = [{"Key": o["Key"]} for o in objs]
            self._client.delete_objects(
                Bucket=self._bucket, Delete={"Objects": keys, "Quiet": True}
            )
            n += len(keys)
        return n

    def exists(self, key: str) -> bool:
        self._check_key(key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def list_prefix(self, prefix: str) -> Iterable[str]:
        self._check_key(prefix)
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for o in page.get("Contents", []):
                yield o["Key"]

    def public_url(self, key: str) -> str:
        self._check_key(key)
        if self._public_base_url:
            # 公开 CDN / 公开 bucket，直接拼接
            return f"{self._public_base_url}/{key}"
        # 否则生成预签名 URL（短时效）
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=self._presign_expires,
            )
        except Exception as e:
            logger.warning("presign failed for {}: {}; fallback to /api/event-files", key, e)
            return f"/api/event-files/{key}"

    def backend_name(self) -> str:
        return "s3"


# ----------------------------------------------------------------------
# 单例
# ----------------------------------------------------------------------


_storage: Optional[Storage] = None


class FallbackStorage(Storage):
    """S3 优先，失败时自动回落本地存储的组合后端。

    主要用于：用户在 .env 中保留了 s3 配置但服务端当前不可达，
    让 CRUD 操作不直接 500，而是悄悄改写到本地 data/ 目录。
    """

    def __init__(self, primary: Storage, fallback: Storage) -> None:
        self._primary = primary
        self._fallback = fallback

    @staticmethod
    def _is_connection_error(exc: BaseException) -> bool:
        """判断异常是否属于"连通性问题"。"""
        # boto3 在不可达时会抛 botocore.exceptions.EndpointConnectionError /
        # ConnectionError / OSError 等；这里用名字粗略判断
        name = exc.__class__.__name__
        if name in {
            "EndpointConnectionError",
            "ConnectTimeoutError",
            "ReadTimeoutError",
            "ConnectionError",
            "ConnectionClosedError",
            "SSLError",
            "OSError",
        }:
            return True
        # urllib3 的底层异常
        msg = str(exc).lower()
        if any(
            k in msg
            for k in (
                "connection refused",
                "could not connect",
                "timed out",
                "timeout",
                "name or service not known",
                "no route to host",
                "failed to establish",
                "network is unreachable",
            )
        ):
            return True
        return False

    # ---- 写入 ----
    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> None:
        try:
            self._primary.put_bytes(key, data, content_type)
            return
        except Exception as e:
            if not self._is_connection_error(e):
                raise
            logger.warning(
                "primary storage unavailable for put_bytes({}), fallback to local: {}",
                key, e,
            )
        self._fallback.put_bytes(key, data, content_type)

    def put_file(self, key: str, src_path: Path, content_type: Optional[str] = None) -> None:
        try:
            self._primary.put_file(key, src_path, content_type)
            return
        except Exception as e:
            if not self._is_connection_error(e):
                raise
            logger.warning(
                "primary storage unavailable for put_file({}), fallback to local: {}",
                key, e,
            )
        self._fallback.put_file(key, src_path, content_type)

    # ---- 读取 ----
    def get_bytes(self, key: str) -> bytes:
        try:
            return self._primary.get_bytes(key)
        except FileNotFoundError:
            raise
        except Exception as e:
            if not self._is_connection_error(e):
                raise
            logger.warning("primary get_bytes({}) failed, fallback to local: {}", key, e)
            return self._fallback.get_bytes(key)

    def open_read(self, key: str) -> BinaryIO:
        try:
            return self._primary.open_read(key)
        except FileNotFoundError:
            raise
        except Exception as e:
            if not self._is_connection_error(e):
                raise
            logger.warning("primary open_read({}) failed, fallback to local: {}", key, e)
            return self._fallback.open_read(key)

    # ---- 删除 ----
    def delete(self, key: str) -> None:
        # 写入回落到本地后，删除也要同时清本地
        try:
            self._primary.delete(key)
        except Exception as e:
            if not self._is_connection_error(e):
                raise
            logger.warning("primary delete({}) failed, will still try local: {}", key, e)
        try:
            self._fallback.delete(key)
        except Exception:
            pass

    def delete_prefix(self, prefix: str) -> int:
        n = 0
        try:
            n += self._primary.delete_prefix(prefix)
        except Exception as e:
            if not self._is_connection_error(e):
                raise
            logger.warning("primary delete_prefix({}) failed, fallback to local: {}", prefix, e)
        try:
            n += self._fallback.delete_prefix(prefix)
        except Exception:
            pass
        return n

    # ---- 元信息 ----
    def exists(self, key: str) -> bool:
        if self._primary.exists(key):
            return True
        try:
            return self._fallback.exists(key)
        except Exception:
            return False

    def list_prefix(self, prefix: str) -> Iterable[str]:
        seen: set[str] = set()
        try:
            for k in self._primary.list_prefix(prefix):
                seen.add(k)
                yield k
        except Exception as e:
            if not self._is_connection_error(e):
                raise
            logger.warning("primary list_prefix({}) failed, fallback to local: {}", prefix, e)
        try:
            for k in self._fallback.list_prefix(prefix):
                if k not in seen:
                    yield k
        except Exception:
            pass

    def public_url(self, key: str) -> str:
        # 公开 URL 仍优先用 S3 风格；若 S3 不可达则 fallback 给出 /api/event-files/<key>
        try:
            return self._primary.public_url(key)
        except Exception as e:
            if not self._is_connection_error(e):
                raise
            return self._fallback.public_url(key)

    def backend_name(self) -> str:
        return f"{self._primary.backend_name()}+fallback({self._fallback.backend_name()})"


def get_storage() -> Storage:
    """按 settings 返回当前存储后端单例。

    当 storage_backend=s3 时，自动套一层 FallbackStorage，s3 不可达时
    静默回落到本地 data/ 目录，避免 CRUD 直接 500。
    """
    global _storage
    if _storage is not None:
        return _storage
    if settings.storage_backend == "s3":
        primary = S3Storage(
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            path_style=settings.s3_path_style,
            public_base_url=settings.s3_public_base_url or None,
            presign_expires=settings.s3_presign_expires,
        )
        fallback = LocalStorage(settings.storage_local_root)
        _storage = FallbackStorage(primary, fallback)
        logger.info(
            "Storage: S3-compatible ({}://{}/{}) with local fallback to {}",
            settings.s3_endpoint_url, settings.s3_bucket, '',
            settings.storage_local_root,
        )
    elif settings.storage_backend == "local":
        _storage = LocalStorage(settings.storage_local_root)
        logger.info("Storage: local ({})", settings.storage_local_root)
    else:
        raise RuntimeError(f"unknown storage_backend: {settings.storage_backend!r}")
    return _storage


def reset_storage() -> None:
    """用于测试时重新构建存储单例。"""
    global _storage
    _storage = None