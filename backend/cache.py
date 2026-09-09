"""全媒体聚合平台 - Redis 缓存（未配置时内存降级）"""
import json
import time

import redis as redis_lib

from config import get as cfg_get
from logger import get_logger

logger = get_logger(__name__)

_client = None
_available = None
_memory = {}


def _get_client():
    global _client, _available
    if _available is not None:
        return _client if _available else None
    url = cfg_get("REDIS_URL", "")
    if not url:
        _available = False
        return None
    try:
        c = redis_lib.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        c.ping()
        _client = c
        _available = True
    except Exception:
        _available = False
    return _client if _available else None


def get_json(key: str, default=None):
    c = _get_client()
    if c is not None:
        try:
            raw = c.get(key)
            return json.loads(raw) if raw else default
        except Exception:
            return default
    item = _memory.get(key)
    if item and (item.get("expire_at") is None or item["expire_at"] > time.time()):
        return item.get("value", default)
    return default


def set_json(key: str, value, ttl: int = 3600):
    c = _get_client()
    if c is not None:
        try:
            c.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            return True
        except Exception:
            return False
    _memory[key] = {"value": value, "expire_at": time.time() + ttl}
    return True


def delete(key: str):
    c = _get_client()
    if c is not None:
        try:
            c.delete(key)
        except Exception:
            pass
    _memory.pop(key, None)
