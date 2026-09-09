"""全媒体聚合平台 - 热点新闻路由"""
import hashlib
from datetime import datetime, timedelta
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from database import SessionLocal, engine, get_db
from deps import get_token_payload, require_editor
from models import News
from schemas import CrawlResponse, NewsBase, NewsListResponse
from spider import NewsSpider

router = APIRouter(prefix="/api/news", tags=["热点新闻"])

# 后台抓取状态（进程内；生产可换 Redis）
_crawl_state = {
    "running": False,
    "progress": {},
    "total": 0,
    "new_count": 0,
    "started_at": None,
    "finished_at": None,
    "error": "",
}
_crawl_lock = threading.Lock()
_fts_state = {"checked": False, "ok": False}


def _hash_title(title: str) -> str:
    return hashlib.sha1((title or "").encode("utf-8")).hexdigest()


def _fts_supported() -> bool:
    """MySQL FULLTEXT(ngram) 是否可用（探测一次并缓存）。"""
    if _fts_state["checked"]:
        return _fts_state["ok"]
    _fts_state["checked"] = True
    try:
        if not engine.dialect.name.startswith("mysql"):
            _fts_state["ok"] = False
            return False
        with engine.connect() as conn:
            row = conn.execute(text(
                "SHOW INDEX FROM news WHERE Key_name = 'ft_news_title_summary'"
            )).fetchone()
            _fts_state["ok"] = row is not None
    except Exception:
        _fts_state["ok"] = False
    return _fts_state["ok"]


def apply_keyword_filter(query, keyword: str):
    """关键词过滤：MySQL 走 FULLTEXT(ngram)，其他引擎回退 LIKE。"""
    if not keyword:
        return query
    if _fts_supported():
        return query.filter(
            text("MATCH (title, summary) AGAINST (:kw IN NATURAL LANGUAGE MODE)")
            .bindparams(kw=keyword)
        )
    like = f"%{keyword}%"
    return query.filter((News.title.like(like)) | (News.summary.like(like)))


def start_crawl() -> bool:
    """启动后台抓取；已在运行时返回 False。"""
    with _crawl_lock:
        if _crawl_state["running"]:
            return False
        _crawl_state.update(
            running=True, progress={}, total=0, new_count=0,
            started_at=datetime.utcnow().isoformat(), finished_at=None, error="",
        )
    threading.Thread(target=_run_crawl, daemon=True).start()
    return True


def _run_crawl():
    global _crawl_state
    spider = NewsSpider()
    db = SessionLocal()
    new_count = 0
    collected = {}
    try:
        def _progress(key, count):
            _crawl_state["progress"] = {**_crawl_state["progress"], key: count}

        collected = spider.crawl_all(progress_cb=_progress)
        items_by_hash = {}
        for source_key, items in collected.items():
            for it in items:
                h = _hash_title(it["title"])
                if h not in items_by_hash:
                    items_by_hash[h] = it
        hashes = list(items_by_hash.keys())
        if hashes:
            existing = {
                r[0] for r in db.query(News.title_hash)
                .filter(News.title_hash.in_(hashes)).all()
            }
            for h, it in items_by_hash.items():
                if h in existing:
                    continue
                db.add(News(
                    title=it["title"], summary=it["summary"], source=it["source"],
                    source_name=it["source_name"], url=it["url"], image_url=it["image_url"],
                    heat_score=it["heat_score"], rank=it["rank"], category=it["category"],
                    title_hash=h,
                ))
                new_count += 1
        db.commit()
        _crawl_state["total"] = sum(len(v) for v in collected.values())
        _crawl_state["new_count"] = new_count
    except Exception as e:
        _crawl_state["error"] = str(e)[:500]
    finally:
        db.close()
        _crawl_state["running"] = False
        _crawl_state["finished_at"] = datetime.utcnow().isoformat()


def _to_base(n: News) -> NewsBase:
    return NewsBase(
        id=n.id, title=n.title, summary=n.summary or "", source=n.source,
        source_name=n.source_name or n.source, url=n.url or "", image_url=n.image_url or "",
        heat_score=n.heat_score or 0, rank=n.rank or 0, category=n.category or "综合",
        published_at=n.published_at, created_at=n.created_at,
    )


@router.get("", response_model=NewsListResponse)
def list_news(
    source: Optional[str] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    sort: str = "time",
    days: Optional[int] = Query(3, ge=1, le=30),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    query = db.query(News)
    if source:
        query = query.filter(News.source == source)
    if category:
        query = query.filter(News.category == category)
    if keyword:
        query = apply_keyword_filter(query, keyword)
    # 默认只展示最近 N 天（默认 3 天）热点
    if days:
        query = query.filter(News.created_at >= datetime.utcnow() - timedelta(days=days))
    total = query.count()
    order = desc(News.heat_score) if sort == "heat" else desc(News.published_at)
    rows = query.order_by(order).offset((page - 1) * page_size).limit(page_size).all()
    return NewsListResponse(items=[_to_base(n) for n in rows], total=total, page=page, page_size=page_size)


@router.get("/top", response_model=list[NewsBase])
def top_news(
    limit: int = Query(10, ge=1, le=50),
    days: Optional[int] = Query(3, ge=1, le=30),
    user: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    query = db.query(News)
    if days:
        query = query.filter(News.created_at >= datetime.utcnow() - timedelta(days=days))
    rows = query.order_by(desc(News.heat_score)).limit(limit).all()
    return [_to_base(n) for n in rows]


@router.get("/{news_id}", response_model=NewsBase)
def news_detail(news_id: int, user: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    return _to_base(news)


@router.post("/crawl")
def crawl_news(user: dict = Depends(require_editor)):
    """异步触发抓取（后台线程执行，立即返回）。"""
    if not start_crawl():
        return {"running": True, "message": "抓取已在后台运行中"}
    return {"running": True, "message": "抓取任务已启动，可查询状态"}


@router.get("/crawl/status")
def crawl_status(user: dict = Depends(get_token_payload)):
    """查询后台抓取状态与进度。"""
    return {
        "running": _crawl_state["running"],
        "progress": _crawl_state["progress"],
        "total": _crawl_state["total"],
        "new_count": _crawl_state["new_count"],
        "started_at": _crawl_state["started_at"],
        "finished_at": _crawl_state["finished_at"],
        "error": _crawl_state["error"],
    }
