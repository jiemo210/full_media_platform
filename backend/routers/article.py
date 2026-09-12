"""全媒体聚合平台 - AI 文章路由（改写/创作，流式输出，富文本内容）"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session
from typing import Optional

from ai_service import (
    generate_create, generate_create_stream, generate_rewrite,
    generate_rewrite_stream, generate_rewrite_suggestions, markdown_to_html,
    generate_risk_revise_stream, risk_check_content,
)
from article_fetcher import fetch_article
from config import get_write_styles
from config import get as cfg_get
from rate_limit import check_limit, record_hit
from database import get_db
from deps import get_token_payload, require_editor
from logger import get_logger
from models import Article, News
from schemas import (
    ArticleBase, ArticleListResponse, ArticleUpdate,
    CreateRequest, RewriteRequest, ArticleSaveRequest, SuggestionsRequest,
    RiskCheckRequest, RiskReviseRequest,
)

router = APIRouter(prefix="/api/articles", tags=["AI文章"])
logger = get_logger(__name__)


def _check_ai_rate(user: dict):
    """AI 调用限流：按用户/小时。"""
    limit = cfg_get("AI_RATE_LIMIT", 50)
    window = cfg_get("AI_RATE_WINDOW", 1) * 3600
    key = f"ai:rate:{user.get('user_id')}"
    if check_limit(key, limit, window, 1):
        raise HTTPException(status_code=429, detail=f"AI 调用过于频繁：{window // 3600} 小时内最多 {limit} 次")
    record_hit(key, window, 1)


@router.get("/styles")
def list_write_styles(user: dict = Depends(get_token_payload)):
    """写作/改写风格（以维护数据为准）"""
    return {"styles": get_write_styles()}


@router.post("/suggestions")
async def rewrite_suggestions(news_id: int, req: SuggestionsRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """AI 改写建议（供用户勾选带入补充提示词）"""
    _check_ai_rate(user)
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    suggestions = generate_rewrite_suggestions(news.title, news.summary, req.model, req.count)
    return {"news_id": news_id, "suggestions": suggestions}


@router.post("/risk-check")
def risk_check(req: RiskCheckRequest, user: dict = Depends(require_editor)):
    """AI 风控检查：合规审查 + 所选平台风控要求。"""
    if not cfg_get("RISK_CHECK_ENABLED", True):
        return {"enabled": False, "message": "风控检查已关闭（后台可开启）"}
    if not (req.title.strip() or req.content.strip()):
        raise HTTPException(status_code=400, detail="请先填写标题或正文再检查")
    _check_ai_rate(user)
    result = risk_check_content(req.title, req.content, req.platform, cfg_get("RISK_CHECK_EXTRA", ""))
    return {"enabled": True, "platform": req.platform or "", **result}


@router.post("/risk-revise")
async def risk_revise(req: RiskReviseRequest, user: dict = Depends(require_editor)):
    """按风控建议修改文章（SSE 流式，输出改进后的完整 Markdown）。"""
    if not (req.title.strip() or req.content.strip()):
        raise HTTPException(status_code=400, detail="请先填写标题或正文")
    if not (req.issues or req.suggestions):
        raise HTTPException(status_code=400, detail="缺少风控建议，请先执行风控检查")
    _check_ai_rate(user)
    gen = generate_risk_revise_stream(
        req.title, req.content, req.platform,
        req.issues or [], req.suggestions or [], req.model or "",
    )
    return _sse(gen, target_words=max(300, int(_char_count(req.content) * 0.9)),
                title=req.title, style="", platform=req.platform, model=req.model)


def _to_base(a: Article) -> ArticleBase:
    return ArticleBase(
        id=a.id, news_id=a.news_id, title=a.title, content_md=a.content_md or "",
        content_html=a.content_html or "", source_type=a.source_type, style=a.style or "",
        platform=a.platform or "", status=a.status or "draft", created_at=a.created_at,
    )


def _char_count(text: str) -> int:
    return len((text or "").replace("\n", "").replace(" ", "").replace("\t", ""))


def _sse(gen, target_words: int = 0, title: str = "", style: str = "",
         platform: str = "", model: str = ""):
    def event_stream():
        buf = ""
        try:
            for token in gen:
                buf += token
                yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.warning(f"[ai] 生成中断: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'生成中断：{e}'}, ensure_ascii=False)}\n\n"
            return
        # 长文完整性：未达目标 80% 时自动续写（最多 2 轮）
        tries = 0
        while target_words and _char_count(buf) < int(target_words * 0.8) and tries < 2:
            try:
                from ai_service import continue_content
                extra = (continue_content(title or "文章", buf, style, platform, model, target_words) or "").strip()
            except Exception as e:
                logger.warning(f"[ai] 续写失败: {e}")
                break
            if not extra:
                break
            piece = "\n\n" + extra
            buf += piece
            tries += 1
            logger.info(f"[ai] 触发续写第 {tries} 轮，当前字数 {_char_count(buf)}（目标 {target_words}）")
            yield f"data: {json.dumps({'type': 'token', 'content': piece}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'content': buf}, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/rewrite/stream")
async def rewrite_stream(news_id: int, req: RewriteRequest, request: Request, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """热点新闻 AI 改写（SSE 流式）。"""
    _check_ai_rate(user)
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    fetched = fetch_article(news.url, news.summary)
    original = fetched.get("text") or news.summary
    gen = generate_rewrite_stream(news.title, news.summary, original, req.style, req.extra_prompt, req.platform, req.model, req.word_count)
    return _sse(gen, target_words=req.word_count, title=news.title,
                style=req.style, platform=req.platform, model=req.model)


@router.post("/create/stream")
async def create_stream(req: CreateRequest, user: dict = Depends(require_editor)):
    """自定义主题 AI 创作（SSE 流式）。"""
    _check_ai_rate(user)
    gen = generate_create_stream(req.topic, req.style, req.word_count, req.extra_prompt, req.platform, req.model)
    return _sse(gen, target_words=req.word_count, title=req.topic,
                style=req.style, platform=req.platform, model=req.model)


@router.post("/rewrite", response_model=ArticleBase)
async def rewrite_save(news_id: int, req: RewriteRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """热点新闻 AI 改写并保存。"""
    _check_ai_rate(user)
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")
    fetched = fetch_article(news.url, news.summary)
    result = generate_rewrite(news.title, news.summary, fetched.get("text") or news.summary, req.style, req.extra_prompt, req.platform, req.model, req.word_count)
    article = Article(
        news_id=news_id, title=result["title"], content_md=result["content"],
        content_html=markdown_to_html(result["content"]), source_type="rewrite",
        style=req.style, platform=req.platform, user_id=user.get("user_id"),
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return _to_base(article)


@router.post("/create", response_model=ArticleBase)
async def create_save(req: CreateRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """自定义主题 AI 创作并保存。"""
    _check_ai_rate(user)
    result = generate_create(req.topic, req.style, req.word_count, req.extra_prompt, req.platform, req.model)
    article = Article(
        title=result["title"], content_md=result["content"],
        content_html=markdown_to_html(result["content"]), source_type="create",
        style=req.style, platform=req.platform, user_id=user.get("user_id"),
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return _to_base(article)


@router.post("/save", response_model=ArticleBase)
def save_from_editor(req: ArticleSaveRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """富文本编辑器保存（AI 已在流式中生成，此处直接入库）。"""
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="标题不能为空")
    article = Article(
        news_id=req.news_id, title=req.title,
        content_md=req.content_md, content_html=req.content_html or markdown_to_html(req.content_md),
        source_type=req.source_type, style=req.style, platform=req.platform,
        user_id=user.get("user_id"),
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return _to_base(article)


@router.get("", response_model=ArticleListResponse)
def list_articles(
    source_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    query = db.query(Article)
    if source_type:
        query = query.filter(Article.source_type == source_type)
    total = query.count()
    rows = query.order_by(desc(Article.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return ArticleListResponse(items=[_to_base(a) for a in rows], total=total, page=page, page_size=page_size)


@router.get("/{article_id}", response_model=ArticleBase)
def article_detail(article_id: int, user: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return _to_base(article)


@router.put("/{article_id}", response_model=ArticleBase)
def update_article(article_id: int, req: ArticleUpdate, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """富文本编辑器保存：更新标题 / Markdown / HTML。"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if req.title is not None:
        article.title = req.title
    if req.content_md is not None:
        article.content_md = req.content_md
    if req.content_html is not None:
        article.content_html = req.content_html
    db.commit()
    db.refresh(article)
    return _to_base(article)


@router.delete("/{article_id}")
def delete_article(article_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    # 级联删除引用该文章的发布任务，避免外键约束导致删除失败
    from models import PublishTask
    db.query(PublishTask).filter(PublishTask.article_id == article_id).delete()
    db.delete(article)
    db.commit()
    return {"message": "文章已删除"}
