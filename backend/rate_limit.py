"""全媒体聚合平台 - 简单限流（Redis 优先，内存兜底）"""
import threading
import time

import redis as redis_lib

from config import get as cfg_get

_mem = {}
_lock = threading.Lock()


def _client():
    url = cfg_get("REDIS_URL", "")
    if not url:
        return None
    try:
        c = redis_lib.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        c.ping()
        return c
    except Exception:
        return None


def _mem_get(key):
    now = time.time()
    with _lock:
        rec = _mem.get(key)
        if not rec or now - rec["start"] >= rec["window"]:
            return {"start": now, "window": 3600, "count": 0}
        return dict(rec)


def _mem_set(key, start, window, count):
    with _lock:
        _mem[key] = {"start": start, "window": window, "count": count}


def check_limit(key: str, limit: int, window_seconds: int, amount: int = 1) -> bool:
    """判断是否超限（不计数）：True 表示将超限，应拦截。"""
    if limit <= 0:
        return False
    r = _client()
    if r is not None:
        try:
            cur = int(r.get(key) or 0)
            ttl = r.ttl(key)
            if ttl < 0:
                cur = 0
            return cur + amount > limit
        except Exception:
            pass
    rec = _mem_get(key)
    return rec["count"] + amount > limit


def record_hit(key: str, window_seconds: int, amount: int = 1):
    """记录一次/多次调用。"""
    r = _client()
    if r is not None:
        try:
            cur = r.incrby(key, amount)
            if cur == amount:
                r.expire(key, window_seconds)
            return
        except Exception:
            pass
    now = time.time()
    rec = _mem_get(key)
    if now - rec["start"] >= rec["window"]:
        _mem_set(key, now, window_seconds, amount)
    else:
        _mem_set(key, rec["start"], rec["window"], rec["count"] + amount)
