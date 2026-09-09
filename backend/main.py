"""
全媒体聚合平台 - FastAPI 后端入口
=================================
功能：
  1. 热点新闻挖掘展示（13 源爬取 + 列表/排行/详情）
  2. 热点新闻 AI 改写 → 发布到各媒体平台
  3. 自定义主题 AI 创作 → 富文本编辑器（Markdown 自动渲染）
"""
import os
import threading
import sys
import time
import secrets
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import get as cfg_get, get_config, is_ai_available
from database import Base, SessionLocal, engine
from logger import get_logger
from models import User
from auth_utils import hash_password, verify_password
from deps import get_token_payload
from config import get_ai_models, get_platforms, get_write_styles
from routers import admin, article, auth, media, news, novel, publish, search
from migrations import ensure_migrations

logger = get_logger(__name__)

# 建表
Base.metadata.create_all(bind=engine)

# 增量迁移（schema_migrations 记录版本）
ensure_migrations()

# 种子数据：默认管理员
def _seed_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            pw = cfg_get("ADMIN_PASSWORD", "")
            if not pw:
                pw = secrets.token_urlsafe(9)
                logger.warning(
                    f"已创建默认管理员 admin，初始密码: {pw}（仅本次输出，登录后强制修改；"
                    "可用 FMP_ADMIN_PASSWORD 环境变量指定初始密码）"
                )
            db.add(User(
                username="admin", password_hash=hash_password(pw),
                role="admin", nickname="管理员", must_change_password=True,
            ))
            db.commit()
            return
        # 存量默认口令账号：标记强制改密
        if verify_password("admin123", admin.password_hash):
            admin.must_change_password = True
            db.commit()
            logger.warning("检测到 admin 仍使用默认口令 admin123，已标记必须修改密码")
    finally:
        db.close()


_seed_admin()

config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动自动爬虫等。"""
    if cfg_get("AUTO_CRAWL", False):
        def _auto_crawl():
            from routers.news import start_crawl
            start_crawl()
            interval = max(int(cfg_get("CRAWL_INTERVAL", 1800) or 1800), 60)
            while True:
                time.sleep(interval)
                if not start_crawl():
                    logger.info("[crawl] 上一轮抓取仍在运行，跳过本轮")
        threading.Thread(target=_auto_crawl, daemon=True).start()
        logger.info(f"自动爬虫已启动（间隔 {cfg_get('CRAWL_INTERVAL', 1800)} 秒）")
    if is_ai_available():
        logger.info(f"AI 服务已配置（模型: {cfg_get('AI_MODEL')}）")
    else:
        logger.warning("AI 服务未配置（.env 设置 FMP_AI_API_KEY）")
    logger.info("全媒体聚合平台后端启动完成")
    yield


app = FastAPI(
    title="全媒体聚合平台 API", version="1.0.0",
    description="热点挖掘 · AI 改写 · 全媒体发布", lifespan=lifespan,
)


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    """请求访问日志：方法、路径、状态码、耗时"""
    import time
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000)
    logger.info(f"[access] {request.method} {request.url.path} -> {response.status_code} ({duration}ms)")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get("CORS_ORIGINS", ["http://localhost:5174"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(news.router)
app.include_router(article.router)
app.include_router(publish.router)
app.include_router(admin.router)
app.include_router(media.router)
app.include_router(novel.router)
app.include_router(search.router)

# 本地素材静态访问
_media_dir = cfg_get("MEDIA_DIR", "./media")
os.makedirs(_media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media_dir), name="media")


@app.get("/")
def root():
    return {
        "message": "全媒体聚合平台 API",
        "docs": "/docs",
        "version": "1.0.0",
        "ai_configured": is_ai_available(),
        "sources": list(cfg_get("NEWS_SOURCES", {}).keys()),
    }


@app.get("/api/config")
def public_config(user: dict = Depends(get_token_payload)):
    """公开配置：每页数量、风格库、可用模型、发布平台"""
    return {
        "news_page_size": cfg_get("NEWS_PAGE_SIZE", 10),
        "write_styles": get_write_styles(),
        "ai_models": [{"key": m.get("key"), "name": m.get("name")} for m in get_ai_models() if m.get("enabled", True)],
        "platforms": get_platforms(),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=cfg_get("HOST", "0.0.0.0"), port=cfg_get("PORT", 8000), reload=True)
