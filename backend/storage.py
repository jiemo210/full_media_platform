"""
全媒体聚合平台 - 本地素材存储（对象存储抽象）
============================================
本地磁盘实现，静态挂载于 /media；后续可扩展 MinIO/OSS 适配器。
"""
import os
import uuid

from config import get as cfg_get
from logger import get_logger

logger = get_logger(__name__)


class BaseStorage:
    def save_bytes(self, data: bytes, filename: str = "", subdir: str = "") -> str:
        raise NotImplementedError

    def read(self, path: str) -> bytes:
        raise NotImplementedError

    def delete(self, path: str) -> bool:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        raise NotImplementedError

    def url_for(self, path: str) -> str:
        raise NotImplementedError


class LocalStorage(BaseStorage):
    def __init__(self, base_dir=None):
        self.base_dir = os.path.abspath(base_dir or cfg_get("MEDIA_DIR", "./media"))
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"[storage] 素材目录: {self.base_dir}")

    def _resolve(self, path: str) -> str:
        full = os.path.normpath(os.path.join(self.base_dir, path.lstrip("/")))
        if not full.startswith(self.base_dir):
            raise ValueError("路径越界")
        return full

    def save_bytes(self, data: bytes, filename: str = "", subdir: str = "images") -> str:
        folder = os.path.join(self.base_dir, subdir)
        os.makedirs(folder, exist_ok=True)
        filename = filename or uuid.uuid4().hex
        rel = os.path.join(subdir, filename)
        with open(self._resolve(rel), "wb") as f:
            f.write(data)
        return rel.replace("\\", "/")

    def read(self, path: str) -> bytes:
        with open(self._resolve(path), "rb") as f:
            return f.read()

    def delete(self, path: str) -> bool:
        try:
            os.remove(self._resolve(path))
            return True
        except FileNotFoundError:
            return False

    def exists(self, path: str) -> bool:
        return os.path.exists(self._resolve(path))

    def url_for(self, path: str) -> str:
        return "/media/" + path.lstrip("/")


_storage = None


def get_storage() -> BaseStorage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def reset_storage():
    global _storage
    _storage = None
