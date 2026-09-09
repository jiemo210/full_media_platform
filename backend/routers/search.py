"""全媒体聚合平台 - 资料搜索路由（AI 扩词 + Bing/本地热点检索 + AI 精选）"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from config import get as cfg_get
from database import get_db
from deps import require_editor
from models import News
from routers.news import apply_keyword_filter
from schemas import MaterialSearchRequest
from search_service import (
    ai_expand_queries, ai_refine, filter_by_recency, is_news_article, web_search,
)
from rate_limit import check_limit, record_hit

router = APIRouter(prefix="/api/search", tags=["资料搜索"])


def _check_search_rate(user: dict):
    """资料搜索：AI 扩词+精选共约 2 次调用，按用户/小时限流。"""
    limit = cfg_get("AI_RATE_LIMIT", 50)
    window = cfg_get("AI_RATE_WINDOW", 1) * 3600
    key = f"ai:rate:{user.get('user_id')}"
    if check_limit(key, limit, window, 2):
        raise HTTPException(status_code=429, detail=f"AI 调用过于频繁：{window // 3600} 小时内最多 {limit} 次")
    record_hit(key, window, 2)


@router.post("/materials")
def search_materials(req: MaterialSearchRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """根据输入内容搜索相关新闻与热点资料并展示。"""
    query = (req.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="请输入要搜索的内容")
    days = req.days if req.days is not None else 0
    if days < 0 or days > 365:
        raise HTTPException(status_code=400, detail="时间范围仅支持 0-365 天")
    _check_search_rate(user)

    # 1) AI 扩展检索词（失败回退原文）
    queries = ai_expand_queries(query)

    # 2) 网页检索（360 优先，Bing 兜底，尽力而为）
    web_items = []
    seen_urls = set()
    for q in queries[:3]:
        for it in web_search(q, limit=6):
            url = it.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            # 只保留新闻/文章类
            if not is_news_article(it.get("title", ""), url):
                continue
            it["kind"] = "web"
            web_items.append(it)
        if len(web_items) >= 15:
            break
    web_items = web_items[:15]
    # 时间过滤（显式日期早于窗口的剔除）
    web_items = filter_by_recency(web_items, days)

    # 3) 本地热点库检索（按时间范围过滤，相关性优先）
    local_items = []
    try:
        local_q = apply_keyword_filter(db.query(News), query)
        if days > 0:
            local_q = local_q.filter(News.created_at >= datetime.utcnow() - timedelta(days=days))
        rows = local_q.order_by(desc(News.created_at)).limit(8).all()
        for n in rows:
            local_items.append({
                "title": n.title or "",
                "url": n.url or "",
                "snippet": n.summary or "",
                "source": n.source_name or n.source or "本地热点",
                "source_name": n.source_name or n.source or "本地热点",
                "kind": "local",
                "heat": n.heat_score or 0,
            })
    except Exception:
        pass

    combined = web_items + local_items
    if not combined:
        return {
            "query": query,
            "queries": queries,
            "summary": "未检索到相关资料，可尝试更换关键词或稍后重试。",
            "related_queries": [],
            "items": [],
        }

    # 4) AI 精选与摘要
    refined = ai_refine(query, combined, days)
    pick_map = {p.get("index"): p for p in refined.get("picks") or []}
    items = []
    for i, it in enumerate(combined):
        pick = pick_map.get(i)
        items.append({
            **it,
            "is_hot": bool(pick.get("is_hot")) if pick else False,
            "reason": (pick.get("reason") or "") if pick else "",
            "matched": i in pick_map,
        })
    return {
        "query": query,
        "days": days,
        "queries": queries,
        "summary": refined.get("summary") or f"共检索到 {len(items)} 条相关资料，其中本地热点 {len(local_items)} 条。",
        "related_queries": refined.get("related_queries") or [],
        "web_count": len(web_items),
        "local_count": len(local_items),
        "items": items,
    }
