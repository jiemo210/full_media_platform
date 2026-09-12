"""全媒体聚合平台 - 后台管理路由（统计 / 用户 / 新闻 / 源管理 / 日志）"""
from datetime import datetime
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session
from typing import Optional

from config import (
    get_ai_models, get_news_sources, get_platforms, get_write_styles,
    mask_api_key, update_config, update_news_sources, update_platforms,
)
from database import get_db
from deps import require_admin
from models import Article, News, PublishTask, User
from schemas import AIModelItem, ConfigUpdate, SourceUpdate, StatsResponse, StyleItem, UserCreate, UserUpdate
from auth_utils import hash_password
from spider import NewsSpider
from logger import get_logger

logger = get_logger(__name__)


def _masked_models(models: list) -> list:
    return [
        {**m, "api_key": mask_api_key(m.get("api_key", "")) if m.get("api_key") else ""}
        for m in models
    ]

router = APIRouter(prefix="/api/admin", tags=["后台管理"])


@router.get("/stats", response_model=StatsResponse)
def stats(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    last_crawl = db.query(News).order_by(News.created_at.desc()).first()
    return StatsResponse(
        total_news=db.query(News).count(),
        total_articles=db.query(Article).count(),
        total_publish_tasks=db.query(PublishTask).count(),
        last_crawl_time=last_crawl.created_at.isoformat() if last_crawl else None,
        sources=get_news_sources(),
    )


@router.get("/sources")
def sources(user: dict = Depends(require_admin)):
    return {"sources": get_news_sources()}


@router.put("/sources")
def save_sources(req: SourceUpdate, user: dict = Depends(require_admin)):
    """更新新闻源配置（启用/禁用/移除失效源）。"""
    update_news_sources(req.sources)
    return {"message": "新闻源配置已保存", "sources": req.sources}


@router.post("/sources/health")
def source_health(user: dict = Depends(require_admin)):
    """探测所有源可用性，便于移除失效源。"""
    result = NewsSpider().health_check()
    return {"health": result}


# ============ 用户管理 ============

@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total = db.query(User).count()
    users = db.query(User).order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "users": [
            {"id": u.id, "username": u.username, "role": u.role, "nickname": u.nickname or "", "is_active": u.is_active, "created_at": u.created_at}
            for u in users
        ],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/users")
def create_user(req: UserCreate, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    u = User(username=req.username, password_hash=hash_password(req.password), role=req.role, nickname=req.nickname)
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"message": "用户创建成功", "id": u.id}


@router.put("/users/{user_id}")
def update_user(user_id: int, req: UserUpdate, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.nickname is not None:
        target.nickname = req.nickname
    if req.role is not None:
        target.role = req.role
    if req.is_active is not None:
        target.is_active = req.is_active
    if req.password:
        target.password_hash = hash_password(req.password)
    db.commit()
    return {"message": "用户已更新"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.username == "admin":
        raise HTTPException(status_code=400, detail="不能删除内置管理员")
    db.delete(target)
    db.commit()
    return {"message": "用户已删除"}


# ============ 新闻管理 ============

@router.get("/news")
def admin_list_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    source: Optional[str] = None,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(News)
    if keyword:
        from routers.news import apply_keyword_filter
        query = apply_keyword_filter(query, keyword)
    if source:
        query = query.filter(News.source == source)
    total = query.count()
    rows = query.order_by(desc(News.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [
        {"id": n.id, "title": n.title, "source_name": n.source_name, "source": n.source, "category": n.category,
         "heat_score": n.heat_score, "created_at": n.created_at}
        for n in rows
    ], "total": total, "page": page, "page_size": page_size}


@router.delete("/news/{news_id}")
def admin_delete_news(news_id: int, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    # 解除文章/任务的引用后删除
    db.query(Article).filter(Article.news_id == news_id).update({"news_id": None})
    db.query(PublishTask).filter(PublishTask.news_id == news_id).update({"news_id": None})
    db.delete(news)
    db.commit()
    return {"message": "新闻已删除"}


# ============ 日志查看 ============

@router.get("/logs")
def view_logs(lines: int = Query(200, ge=1, le=2000), user: dict = Depends(require_admin)):
    from config import get as cfg_get
    log_path = os.path.join(cfg_get("LOG_DIR", "./logs"), "app.log")
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.readlines()
        return {"logs": "".join(content[-lines:])}
    except OSError:
        return {"logs": ""}


# ============ AI 模型管理 ============

@router.get("/models")
def list_models(user: dict = Depends(require_admin)):
    return {"models": _masked_models(get_ai_models())}


@router.post("/models")
def create_model(req: AIModelItem, user: dict = Depends(require_admin)):
    models = list(get_ai_models())
    if any(m.get("key") == req.key for m in models):
        raise HTTPException(status_code=400, detail="模型 key 已存在")
    if req.is_default:
        for m in models:
            m["is_default"] = False
    models.append(req.dict())
    update_config({"AI_MODELS": models})
    return {"message": "模型已添加", "models": _masked_models(models)}


@router.put("/models/{model_key}")
def update_model(model_key: str, req: AIModelItem, user: dict = Depends(require_admin)):
    models = list(get_ai_models())
    target = next((m for m in models if m.get("key") == model_key), None)
    if not target:
        raise HTTPException(status_code=404, detail="模型不存在")
    if req.is_default:
        for m in models:
            m["is_default"] = False
    idx = models.index(target)
    models[idx] = req.dict()
    if req.key != model_key and any(m.get("key") == req.key for m in models if m is not models[idx]):
        raise HTTPException(status_code=400, detail="模型 key 冲突")
    update_config({"AI_MODELS": models})
    return {"message": "模型已更新", "models": _masked_models(models)}


@router.delete("/models/{model_key}")
def delete_model(model_key: str, user: dict = Depends(require_admin)):
    models = [m for m in get_ai_models() if m.get("key") != model_key]
    if len(models) == len(get_ai_models()):
        raise HTTPException(status_code=404, detail="模型不存在")
    if models and not any(m.get("is_default") for m in models):
        models[0]["is_default"] = True
    update_config({"AI_MODELS": models})
    return {"message": "模型已删除", "models": _masked_models(models)}


# ============ 写作风格管理 ============

@router.get("/styles")
def list_styles(user: dict = Depends(require_admin)):
    return {"styles": get_write_styles()}


@router.post("/styles")
def create_style(req: StyleItem, user: dict = Depends(require_admin)):
    styles = list(get_write_styles())
    if any(s.get("name") == req.name for s in styles):
        raise HTTPException(status_code=400, detail="风格已存在")
    styles.append(req.dict())
    update_config({"WRITE_STYLES": styles})
    return {"message": "风格已添加", "styles": styles}


@router.put("/styles")
def update_styles(req: dict, user: dict = Depends(require_admin)):
    """整体替换风格列表（支持改名/排序）。"""
    styles = req.get("styles", [])
    update_config({"WRITE_STYLES": styles})
    return {"message": "风格列表已保存", "styles": styles}


@router.delete("/styles/{style_name}")
def delete_style(style_name: str, user: dict = Depends(require_admin)):
    styles = [s for s in get_write_styles() if s.get("name") != style_name]
    update_config({"WRITE_STYLES": styles})
    return {"message": "风格已删除", "styles": styles}


# ============ 发布平台管理 ============

@router.get("/platforms")
def list_platforms(user: dict = Depends(require_admin)):
    return {"platforms": get_platforms()}


@router.post("/platforms")
def create_platform(req: dict, user: dict = Depends(require_admin)):
    platforms = list(get_platforms())
    if any(p.get("key") == req.get("key") for p in platforms):
        raise HTTPException(status_code=400, detail="平台 key 已存在")
    req.setdefault("rules", "")
    req.setdefault("jump_url", "")
    req.setdefault("enabled", True)
    req.setdefault("sort", len(platforms) + 1)
    platforms.append(req)
    update_platforms(platforms)
    return {"message": "平台已添加", "platforms": platforms}


@router.put("/platforms")
def update_platforms_list(req: dict, user: dict = Depends(require_admin)):
    """整体替换平台列表（支持改名/排序/启停）。"""
    update_platforms(req.get("platforms", []))
    return {"message": "平台列表已保存", "platforms": req.get("platforms", [])}


@router.put("/platforms/{platform_key}")
def update_platform(platform_key: str, req: dict, user: dict = Depends(require_admin)):
    platforms = list(get_platforms())
    idx = next((i for i, p in enumerate(platforms) if p.get("key") == platform_key), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="平台不存在")
    platforms[idx] = req
    update_platforms(platforms)
    return {"message": "平台已更新", "platforms": platforms}


@router.delete("/platforms/{platform_key}")
def delete_platform(platform_key: str, user: dict = Depends(require_admin)):
    platforms = [p for p in get_platforms() if p.get("key") != platform_key]
    update_platforms(platforms)
    return {"message": "平台已删除", "platforms": platforms}


# ============ 页面/系统配置 ============

EDITABLE_CONFIG_KEYS = [
    "NEWS_PAGE_SIZE", "AUTO_CRAWL", "CRAWL_INTERVAL", "AI_MODEL",
    "MEDIA_DIR", "AI_RATE_LIMIT", "AI_RATE_WINDOW", "PUBLISH_RATE_LIMIT", "PUBLISH_TASK_LIMIT",
    "RISK_CHECK_ENABLED", "RISK_CHECK_EXTRA",
    "PIPELINE_IMAGE_ENABLED", "PIPELINE_IMAGE_MAX", "PIPELINE_DOWNLOAD_IMAGES",
]


@router.get("/config")
def get_admin_config(user: dict = Depends(require_admin)):
    from config import get_config
    cfg = get_config()
    return {"config": {k: cfg.get(k) for k in EDITABLE_CONFIG_KEYS}, "editable_keys": EDITABLE_CONFIG_KEYS}


@router.put("/config")
def put_admin_config(req: ConfigUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.updates.items() if k in EDITABLE_CONFIG_KEYS}
    update_config(updates)
    return {"message": "配置已保存", "config": updates}
