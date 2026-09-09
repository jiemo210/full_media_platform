"""全媒体聚合平台 - 日志模块（按大小轮转，保留 N 天）"""
import os
import logging
from logging.handlers import RotatingFileHandler

from config import get as cfg_get

_configured = False


class _WinAcceptNoiseFilter(logging.Filter):
    """屏蔽 Windows asyncio accept 的 WinError 64 噪音（python/uvicorn 已知问题，非业务错误）。"""
    _NOISE = ("WinError 64", "指定的网络名不再可用", "Accept failed on a socket")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        return not any(n in msg for n in self._NOISE)


def get_logger(name: str = "app") -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        _configure_root()
    return logger


def _configure_root():
    """把处理器挂到根 logger，所有子 logger 都会输出到文件与控制台。"""
    global _configured
    if _configured:
        return
    _configured = True
    # asyncio 事件循环的 accept 异常（WinError 64）是已知噪音，直接在此丢弃
    logging.getLogger("asyncio").addFilter(_WinAcceptNoiseFilter())
    level = logging.INFO
    log_dir = cfg_get("LOG_DIR", "./logs")
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)
    try:
        _cleanup_old_logs()
        fh = RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=cfg_get("LOG_MAX_BYTES", 10485760),
            backupCount=cfg_get("LOG_BACKUP_COUNT", 5),
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass


def _cleanup_old_logs():
    """按 LOG_RETENTION_DAYS 清理过期日志文件。"""
    import time
    try:
        log_dir = cfg_get("LOG_DIR", "./logs")
        days = int(cfg_get("LOG_RETENTION_DAYS", 7) or 7)
        cutoff = time.time() - days * 86400
        for fn in os.listdir(log_dir):
            if not fn.startswith("app.log"):
                continue
            path = os.path.join(log_dir, fn)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        pass
