"""全媒体聚合平台 - 发布路由（半自动发布包 + 模拟直发）"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from config import get_platform, get_platforms
from config import get as cfg_get
from rate_limit import check_limit, record_hit
from database import get_db
from deps import get_token_payload, require_editor
from models import Article, PublishTask
from publish_service import confirm_publish, create_tasks, generate_package, mock_publish
from schemas import PublishRequest, PublishTaskBase, PublishTaskListResponse, PublishTaskUpdate

router = APIRouter(prefix="/api/publish", tags=["发布"])


def _to_base(t: PublishTask) -> PublishTaskBase:
    platform_cfg = get_platform(t.platform)
    return PublishTaskBase(
        id=t.id, platform=t.platform, title=t.title or "", status=t.status,
        content=t.content or "",
        package_text=t.package_text or "", external_url=t.external_url or "",
        fail_reason=t.fail_reason or "", jump_url=platform_cfg.get("jump_url", ""),
        created_at=t.created_at,
    )


@router.get("/platforms")
def platforms(user: dict = Depends(get_token_payload)):
    return get_platforms()


@router.post("/tasks", response_model=list[PublishTaskBase])
def create_publish_tasks(req: PublishRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    if not req.platforms:
        raise HTTPException(status_code=400, detail="请至少选择一个发布平台")
    count = len(req.platforms)
    # 发布频率限制（按用户/小时）
    rate_limit = cfg_get("PUBLISH_RATE_LIMIT", 50)
    rate_key = f"publish:rate:{user.get('user_id')}"
    if check_limit(rate_key, rate_limit, 3600, count):
        raise HTTPException(status_code=429, detail=f"发布过于频繁：1 小时内最多创建 {rate_limit} 个发布任务")
    # 发布任务总数上限
    task_limit = cfg_get("PUBLISH_TASK_LIMIT", 500)
    total_tasks = db.query(PublishTask).count()
    if total_tasks + count > task_limit:
        raise HTTPException(status_code=429, detail=f"发布任务总数已达上限（{task_limit}），请先清理任务")
    record_hit(rate_key, 3600, count)
    article = None
    if req.article_id:
        article = db.query(Article).filter(Article.id == req.article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        title = req.title or article.title
        content = req.content or article.content_md
    else:
        title = req.title
        content = req.content
    tasks = create_tasks(
        db, user.get("user_id"), title, content, req.platforms,
        article_id=article.id if article else None, news_id=req.news_id or (article.news_id if article else None),
    )
    return [_to_base(t) for t in tasks]


@router.get("/tasks", response_model=PublishTaskListResponse)
def list_tasks(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    query = db.query(PublishTask)
    if status:
        query = query.filter(PublishTask.status == status)
    total = query.count()
    rows = query.order_by(desc(PublishTask.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return PublishTaskListResponse(items=[_to_base(t) for t in rows], total=total, page=page, page_size=page_size)


@router.get("/tasks/{task_id}", response_model=PublishTaskBase)
def task_detail(task_id: int, user: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _to_base(task)


@router.post("/tasks/{task_id}/publish")
def publish_task(task_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """发布跳转：标记已发布并返回平台跳转链接，由前端自动打开。"""
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = mock_publish(db, task)
    jump_url = get_platform(task.platform).get("jump_url", "")
    return {"task": _to_base(task), "jump_url": jump_url}


@router.post("/tasks/{task_id}/confirm")
def confirm_task(task_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """用户确认已在平台完成发布：jumped -> published。"""
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "jumped":
        raise HTTPException(status_code=400, detail="仅「已跳转」状态的任务可确认发布")
    task = confirm_publish(db, task)
    return {"task": _to_base(task)}


@router.put("/tasks/{task_id}", response_model=PublishTaskBase)
def update_task(task_id: int, req: PublishTaskUpdate, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """编辑发布任务（标题/正文/平台），发布包自动重新生成。"""
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if req.title is not None:
        task.title = req.title
    if req.content is not None:
        task.content = req.content
    if req.platform is not None:
        task.platform = req.platform
    if task.status in ("published", "jumped"):
        task.status = "pending"
        task.external_url = ""
    task.package_text = generate_package(task.title, task.content, task.platform)
    db.commit()
    db.refresh(task)
    return _to_base(task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.delete(task)
    db.commit()
    return {"message": "发布任务已删除"}
