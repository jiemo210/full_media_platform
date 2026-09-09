"""
全媒体聚合平台 - 统一配置模块
优先级：config.json < .env < 系统环境变量
"""
import os
import json
import sys

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_config_cache = None
_file_cache = {}


def _load_env_file():
    if not os.path.exists(_ENV_FILE):
        return
    try:
        with open(_ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        pass


_ENV_KEY_MAP = {
    "FMP_DB_ENGINE": "DB_ENGINE",
    "FMP_AI_API_KEY": "AI_API_KEY",
    "FMP_AI_BASE_URL": "AI_BASE_URL",
    "FMP_AI_MODEL": "AI_MODEL",
    "FMP_ADMIN_PASSWORD": "ADMIN_PASSWORD",
    "FMP_JWT_SECRET": "JWT_SECRET",
    "FMP_MYSQL_HOST": "MYSQL_HOST",
    "FMP_MYSQL_PORT": "MYSQL_PORT",
    "FMP_MYSQL_USER": "MYSQL_USER",
    "FMP_MYSQL_PASSWORD": "MYSQL_PASSWORD",
    "FMP_MYSQL_DB": "MYSQL_DB",
    "FMP_DB_PATH": "DB_PATH",
    "FMP_REDIS_URL": "REDIS_URL",
    "FMP_AUTO_CRAWL": "AUTO_CRAWL",
    "FMP_CRAWL_INTERVAL": "CRAWL_INTERVAL",
    "FMP_MEDIA_DIR": "MEDIA_DIR",
    "FMP_AI_RATE_LIMIT": "AI_RATE_LIMIT",
    "FMP_AI_RATE_WINDOW": "AI_RATE_WINDOW",
    "FMP_PUBLISH_RATE_LIMIT": "PUBLISH_RATE_LIMIT",
    "FMP_PUBLISH_TASK_LIMIT": "PUBLISH_TASK_LIMIT",
}


def _apply_env_overrides(cfg):
    _load_env_file()
    for env_key, cfg_key in _ENV_KEY_MAP.items():
        value = os.environ.get(env_key)
        if value is None:
            continue
        if cfg_key in ("MYSQL_PORT", "CRAWL_INTERVAL", "PORT", "JWT_EXPIRE_HOURS", "AI_RATE_LIMIT", "AI_RATE_WINDOW", "PUBLISH_RATE_LIMIT", "PUBLISH_TASK_LIMIT"):
            try:
                cfg[cfg_key] = int(value)
            except ValueError:
                pass
        elif cfg_key == "AUTO_CRAWL":
            cfg[cfg_key] = str(value).strip().lower() in ("1", "true", "yes", "on")
        else:
            cfg[cfg_key] = value
    return cfg


DEFAULTS = {
    "DB_ENGINE": "mysql",
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": 3306,
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "",
    "MYSQL_DB": "full_media",
    "REDIS_URL": "",
    "AI_API_KEY": "",
    "AI_BASE_URL": "https://api.deepseek.com",
    "AI_MODEL": "deepseek-chat",
    "AI_MODELS": [
        {"key": "deepseek-chat", "name": "DeepSeek Chat", "model": "deepseek-chat", "base_url": "", "api_key": "", "enabled": True, "is_default": True},
        {"key": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "model": "deepseek-v4-flash", "base_url": "", "api_key": "", "enabled": True, "is_default": False},
    ],
    "WRITE_STYLES": [
        {"name": "专业深度", "description": "深度分析风格，从多个角度深入剖析"},
        {"name": "简洁快报", "description": "简洁明快的新闻风格，突出关键信息"},
        {"name": "轻松幽默", "description": "轻松活泼的语言风格，幽默风趣"},
        {"name": "深度解读", "description": "深度解读事件背景与影响"},
    ],
    "NEWS_PAGE_SIZE": 10,
    "MEDIA_DIR": "./media",
    "AI_RATE_LIMIT": 50,
    "AI_RATE_WINDOW": 1,
    "PUBLISH_RATE_LIMIT": 50,
    "PUBLISH_TASK_LIMIT": 500,
    "RISK_CHECK_ENABLED": True,
    "RISK_CHECK_EXTRA": "",
    "JWT_SECRET": "full-media-platform-secret-change-me",
    "JWT_EXPIRE_HOURS": 24,
    "AUTO_CRAWL": False,
    "CRAWL_INTERVAL": 1800,
    "NEWS_PER_SOURCE": 20,
    "HOST": "0.0.0.0",
    "PORT": 8000,
    "CORS_ORIGINS": ["http://localhost:5174", "http://127.0.0.1:5174"],
    "LOG_DIR": "./logs",
    "LOG_RETENTION_DAYS": 7,
    "LOG_MAX_BYTES": 10485760,
    "LOG_BACKUP_COUNT": 5,
    # 新闻源（8 个可用源，已剔除失效源）
    "NEWS_SOURCES": {
        "baidu": {"name": "百度新闻", "enabled": True, "news_per_source": 20},
        "toutiao": {"name": "今日头条", "enabled": True, "news_per_source": 20},
        "tencent": {"name": "腾讯新闻", "enabled": True, "news_per_source": 20},
        "cctv": {"name": "央视网", "enabled": True, "news_per_source": 10},
        "sina_finance": {"name": "新浪财经", "enabled": True, "news_per_source": 10},
        "nanfang": {"name": "南方+", "enabled": True, "news_per_source": 10},
        "people": {"name": "人民网", "enabled": True, "news_per_source": 10},
        "xinhua": {"name": "新华网", "enabled": True, "news_per_source": 10},
        "dahe": {"name": "大河网", "enabled": True, "news_per_source": 15},
        "zynews": {"name": "中原网", "enabled": True, "news_per_source": 15},
        "thepaper": {"name": "澎湃新闻", "enabled": True, "news_per_source": 20},
        "hntv": {"name": "大象新闻", "enabled": True, "news_per_source": 15},
        "zhengzhou_fabu": {"name": "郑州发布", "enabled": True, "news_per_source": 10},
    },
    "PLATFORMS": [
        {"key": "toutiao", "label": "今日头条", "min_words": 800, "max_words": 2000, "rules": "标题吸引、段落短、避免营销词汇", "jump_url": "https://mp.toutiao.com/profile_v4/graphic/publish", "enabled": True, "sort": 1},
        {"key": "baijiahao", "label": "百家号", "min_words": 600, "max_words": 1500, "rules": "偏专业、信息密度高、引用来源", "jump_url": "https://baijiahao.baidu.com/builder/rc/edit?type=news", "enabled": True, "sort": 2},
        {"key": "wechat", "label": "微信公众号", "min_words": 1000, "max_words": 3000, "rules": "分段标题、引导关注、适当配图", "jump_url": "https://mp.weixin.qq.com/", "enabled": True, "sort": 3},
        {"key": "zhihu", "label": "知乎", "min_words": 800, "max_words": 3000, "rules": "结构化回答、引用来源、观点清晰", "jump_url": "https://zhuanlan.zhihu.com/write", "enabled": True, "sort": 4},
        {"key": "weibo", "label": "微博", "min_words": 100, "max_words": 500, "rules": "带话题标签、140字内可读、口语化", "jump_url": "https://weibo.com/", "enabled": True, "sort": 5},
        {"key": "xiaohongshu", "label": "小红书", "min_words": 300, "max_words": 1000, "rules": "生活化、emoji、标题党适度、标签", "jump_url": "https://creator.xiaohongshu.com/publish/publish", "enabled": True, "sort": 6},
        {"key": "bilibili", "label": "B站动态", "min_words": 100, "max_words": 800, "rules": "标题党适可、带链接、避免外链过多", "jump_url": "https://www.bilibili.com/", "enabled": True, "sort": 7},
        {"key": "weitoutiao", "label": "微头条", "min_words": 200, "max_words": 500, "rules": "口语化、带话题、短平快", "jump_url": "https://mp.toutiao.com/profile_v4/graphic/publish", "enabled": True, "sort": 8},
    ],
}


def get_config() -> dict:
    global _config_cache, _file_cache
    if _config_cache is not None:
        return _config_cache
    cfg = dict(DEFAULTS)
    cfg["NEWS_SOURCES"] = {k: dict(v) for k, v in DEFAULTS["NEWS_SOURCES"].items()}
    cfg["PLATFORMS"] = [dict(p) for p in DEFAULTS["PLATFORMS"]]
    _file_cache = {}
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _file_cache = data
        for key, value in data.items():
            if key in cfg:
                cfg[key] = value
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    _apply_env_overrides(cfg)
    _config_cache = cfg
    return _config_cache


def get(key: str, default=None):
    return get_config().get(key, default)


def get_news_sources() -> dict:
    return get_config().get("NEWS_SOURCES", {})


def update_news_sources(sources: dict) -> dict:
    cfg = get_config()
    cfg["NEWS_SOURCES"] = sources
    persist = dict(_file_cache or {})
    persist["NEWS_SOURCES"] = sources
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(persist, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return sources


def get_platforms() -> list:
    return get_config().get("PLATFORMS", [])


def update_platforms(platforms: list) -> list:
    cfg = get_config()
    cfg["PLATFORMS"] = platforms
    persist = dict(_file_cache or {})
    persist["PLATFORMS"] = platforms
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(persist, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return platforms


def get_platform(key_or_label: str) -> dict:
    """按平台 key 或显示名称查找（发布任务中保存的是名称）。"""
    for p in get_platforms():
        if p.get("key") == key_or_label or p.get("label") == key_or_label:
            return p
    return {}


def get_ai_models() -> list:
    return get_config().get("AI_MODELS", [])


def get_write_styles() -> list:
    return get_config().get("WRITE_STYLES", [])


def update_config(updates: dict) -> dict:
    """更新配置并持久化到 config.json（过滤脱敏占位值，避免密钥被写坏）。"""
    global _config_cache, _file_cache
    cfg = get_config()
    clean = {}
    for k, v in updates.items():
        if isinstance(v, str) and v.endswith("****") and k in ("AI_API_KEY",):
            continue
        clean[k] = v
    # AI_MODELS：api_key 为空或以 **** 结尾视为“保持不变”，保留内存中的原值
    if "AI_MODELS" in clean and isinstance(clean["AI_MODELS"], list):
        old_models = {m.get("key"): m for m in cfg.get("AI_MODELS", [])}
        merged = []
        for m in clean["AI_MODELS"]:
            nm = dict(m)
            raw_key = str(nm.get("api_key") or "")
            if not raw_key or raw_key.endswith("****"):
                nm["api_key"] = (old_models.get(nm.get("key")) or {}).get("api_key", "")
            merged.append(nm)
        clean["AI_MODELS"] = merged
    cfg.update(clean)
    persist = dict(_file_cache or {})
    persist.update(_sanitize_for_persist(clean))
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(persist, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return cfg


def _sanitize_for_persist(value):
    """config.json 不落盘 API Key：内存中保留，重启后从 .env / 环境变量读取。"""
    if isinstance(value, dict):
        out = dict(value)
        if "api_key" in out:
            out["api_key"] = ""
        return {k: _sanitize_for_persist(v) for k, v in out.items()}
    if isinstance(value, list):
        return [_sanitize_for_persist(v) for v in value]
    return value


def mask_api_key(key: str) -> str:
    """脱敏展示：sk-abc****wxyz。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


_WEAK_JWT_SECRETS = {
    "full-media-platform-secret-change-me",
    "full-media-secret",
    "full-media-platform-secret-2026",
}
_jwt_secret_fallback = None


def get_jwt_secret() -> str:
    """JWT 密钥：优先环境变量；发现弱默认值时自动生成随机密钥并告警。"""
    global _jwt_secret_fallback
    secret = get("JWT_SECRET", "")
    if secret and secret not in _WEAK_JWT_SECRETS:
        return secret
    if _jwt_secret_fallback is None:
        import secrets
        _jwt_secret_fallback = secrets.token_urlsafe(48)
        try:
            from logger import get_logger
            get_logger(__name__).warning("JWT_SECRET 缺失或为弱默认值，已生成随机密钥（重启后旧 Token 失效）")
        except Exception:
            pass
    return _jwt_secret_fallback


def is_ai_available() -> bool:
    return bool(get("AI_API_KEY", ""))


def get_db_url() -> str:
    if get("DB_ENGINE", "mysql") == "sqlite":
        return f"sqlite:///{get('DB_PATH', './full_media.db')}"
    return (f"mysql+pymysql://{get('MYSQL_USER', 'root')}:{get('MYSQL_PASSWORD', '')}"
            f"@{get('MYSQL_HOST', '127.0.0.1')}:{get('MYSQL_PORT', 3306)}/{get('MYSQL_DB', 'full_media')}?charset=utf8mb4")
