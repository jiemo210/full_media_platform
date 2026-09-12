"""全媒体聚合平台 - 一键成稿任务流路由"""
import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from config import get_platforms
from database import SessionLocal, get_db
from deps import get_token_payload, require_editor
from models import News, PipelineRun, PipelineStageArtifact
from pipeline_service import (
    ensure_worker_started, events_after, planned_stages, publish_event, run_dict,
)
from schemas import PipelineRunCreate

router = APIRouter(prefix="/api/pipeline", tags=["一键成稿"])

_TERMINAL = {"completed", "failed", "cancelled"}


def _get_run_or_404(db: Session, run_id: int, user: dict) -> PipelineRun:
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="任务不存在")
    if run.user_id != user.get("user_id") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return run


def _load_with_news(db: Session, runs: list) -> list:
    news_ids = {r.news_id for r in runs if r.news_id}
    titles = {}
    if news_ids:
        for n in db.query(News).filter(News.id.in_(news_ids)).all():
            titles[n.id] = n.title
    # 阶段进度（列表展示用）
    progress = {}
    run_ids = [r.id for r in runs]
    if run_ids:
        for rid, st in db.query(PipelineStageArtifact.run_id, PipelineStageArtifact.status) \
                .filter(PipelineStageArtifact.run_id.in_(run_ids)).all():
            agg = progress.setdefault(rid, {"done": 0, "total": 0})
            agg["total"] += 1
            if st in ("done", "skipped"):
                agg["done"] += 1
    out = []
    for r in runs:
        item = run_dict(r, news_title=titles.get(r.news_id, ""))
        planned = max(len(planned_stages(r)), progress.get(r.id, {}).get("total", 0))
        done = progress.get(r.id, {}).get("done", 0)
        percent = 100 if r.status == "completed" else (round(done / planned * 100) if planned else 0)
        item["progress"] = {
            "done": done, "total": planned,
            "percent": min(100, max(0, percent)),
        }
        out.append(item)
    return out


@router.post("/runs")
def create_run(req: PipelineRunCreate, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """创建一键成稿任务（异步 Worker 自动执行）。"""
    if req.source_type not in ("rewrite", "create"):
        raise HTTPException(status_code=400, detail="source_type 仅支持 rewrite/create")
    if req.source_type == "rewrite":
        if not req.news_id:
            raise HTTPException(status_code=400, detail="改写任务需要传入热点新闻")
        news = db.query(News).filter(News.id == req.news_id).first()
        if not news:
            raise HTTPException(status_code=404, detail="新闻不存在")
    else:
        if not req.topic.strip():
            raise HTTPException(status_code=400, detail="创作主题不能为空")
        if len(req.topic) > 20000:
            raise HTTPException(status_code=400, detail="创作主题过长（最多 20000 字），请精简或改走素材改写")
    if req.mode != "auto":
        raise HTTPException(status_code=400, detail="当前版本仅支持自动模式（mode=auto）")
    word_count = max(200, min(int(req.word_count or 800), 10000))
    enabled = {p.get("key") or p.get("label") for p in get_platforms() if p.get("enabled")}
    publish_platforms = [p for p in (req.publish_platforms or []) if p in enabled]
    run = PipelineRun(
        user_id=user.get("user_id"),
        source_type=req.source_type,
        news_id=req.news_id,
        topic=(req.topic or "").strip(),
        mode="auto",
        config={
            "style": req.style or "专业深度",
            "word_count": word_count,
            "platform": (req.platform or "").strip(),
            "model": (req.model or "").strip(),
            "extra_prompt": (req.extra_prompt or "").strip()[:2000],
            "auto_fix": bool(req.auto_fix),
            "publish_platforms": publish_platforms,
        },
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    news_title = ""
    if req.news_id:
        news = db.query(News).filter(News.id == req.news_id).first()
        news_title = news.title if news else ""
    ensure_worker_started()
    publish_event(run.id, "run_status", {"status": "queued", "stage": ""})
    return run_dict(run, news_title=news_title)


@router.get("/runs")
def list_runs(
    status: str = Query("", description="按状态过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    query = db.query(PipelineRun)
    if user.get("role") != "admin":
        query = query.filter(PipelineRun.user_id == user.get("user_id"))
    if status and status in {"queued", "running", "completed", "failed", "cancelled"}:
        query = query.filter(PipelineRun.status == status)
    total = query.count()
    rows = query.order_by(desc(PipelineRun.id)).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": _load_with_news(db, rows), "total": total, "page": page, "page_size": page_size}


@router.get("/runs/{run_id}")
def run_detail(
    run_id: int,
    content: int = Query(0, description="是否返回阶段正文"),
    user: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    run = _get_run_or_404(db, run_id, user)
    news_title = ""
    if run.news_id:
        news = db.query(News).filter(News.id == run.news_id).first()
        news_title = news.title if news else ""
    return run_dict(run, with_artifacts=True, include_content=bool(content), news_title=news_title)


@router.get("/runs/{run_id}/events")
def run_events(run_id: int, request: Request, user: dict = Depends(get_token_payload)):
    """SSE：任务进度事件（断线后可用 since 续传）。"""
    db = SessionLocal()
    try:
        run = _get_run_or_404(db, run_id, user)
    finally:
        db.close()
    since = int(request.query_params.get("since", "0") or 0)

    def event_stream():
        cursor = since
        last_activity = time.time()
        try:
            # 任务已结束时，先发一个快照并立即断开，避免客户端反复重连
            sdb = SessionLocal()
            try:
                cur = sdb.query(PipelineRun).filter(PipelineRun.id == run_id).first()
                cur_status = cur.status if cur else "completed"
            finally:
                sdb.close()
            if cur_status in _TERMINAL:
                yield f"data: {json.dumps({'type': 'run_status', 'payload': {'status': cur_status}}, ensure_ascii=False)}\n\n"
                return
            while True:
                for ev in events_after(run_id, cursor):
                    cursor = ev["seq"]
                    last_activity = time.time()
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    if ev["type"] == "run_status" and ev["payload"].get("status") in _TERMINAL:
                        return
                # 心跳 / 重启后兜底快照
                now = time.time()
                sdb = SessionLocal()
                try:
                    cur = sdb.query(PipelineRun).filter(PipelineRun.id == run_id).first()
                    cur_status = cur.status if cur else "completed"
                finally:
                    sdb.close()
                if cur_status in _TERMINAL and now - last_activity > 3:
                    yield f"data: {json.dumps({'type': 'run_status', 'payload': {'status': cur_status}}, ensure_ascii=False)}\n\n"
                    return
                if now - last_activity > 20:
                    yield ": ping\n\n"
                time.sleep(1)
        except GeneratorExit:
            return

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    run = _get_run_or_404(db, run_id, user)
    if run.status not in ("queued", "running"):
        raise HTTPException(status_code=400, detail=f"当前状态（{run.status}）不可取消")
    run.status = "cancelled"
    run.finished_at = datetime.utcnow()
    db.commit()
    publish_event(run_id, "run_status", {"status": "cancelled", "stage": run.current_stage or ""})
    return {"message": "任务已取消（正在执行的 AI 调用将在阶段结束后停止）"}


@router.post("/runs/{run_id}/retry")
def retry_run(run_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    run = _get_run_or_404(db, run_id, user)
    if run.status not in ("failed", "cancelled"):
        raise HTTPException(status_code=400, detail="仅失败/取消的任务可重试")
    db.query(PipelineStageArtifact).filter(
        PipelineStageArtifact.run_id == run_id,
        PipelineStageArtifact.status != "done",
    ).delete(synchronize_session=False)
    run.status = "queued"
    run.error = ""
    run.current_stage = ""
    run.worker_id = ""
    run.finished_at = None
    db.commit()
    ensure_worker_started()
    publish_event(run_id, "run_status", {"status": "queued", "stage": "", "retry": True})
    return {"message": "任务已重新排队"}


@router.delete("/runs/{run_id}")
def delete_run(run_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """删除成稿任务（含阶段产物；已生成的文章仍保留在文章库）。"""
    run = _get_run_or_404(db, run_id, user)
    if run.status in ("queued", "running"):
        raise HTTPException(status_code=400, detail="任务正在执行中，请先取消后再删除")
    try:
        db.query(PipelineStageArtifact).filter(
            PipelineStageArtifact.run_id == run_id
        ).delete(synchronize_session=False)
        db.delete(run)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)[:200]}")
    return {"message": "成稿任务已删除"}


@router.post("/runs/{run_id}/regenerate")
def regenerate_run(run_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """重新生成：按原任务配置复制一个新任务并立即执行（保留原任务记录）。"""
    old = _get_run_or_404(db, run_id, user)
    if old.status in ("queued", "running"):
        raise HTTPException(status_code=400, detail="任务正在执行中，请等待完成或先取消")
    new_run = PipelineRun(
        user_id=user.get("user_id"),
        source_type=old.source_type,
        news_id=old.news_id,
        topic=old.topic or "",
        mode=old.mode or "auto",
        config=dict(old.config or {}),
        status="queued",
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    news_title = ""
    if new_run.news_id:
        news = db.query(News).filter(News.id == new_run.news_id).first()
        news_title = news.title if news else ""
    ensure_worker_started()
    publish_event(new_run.id, "run_status", {"status": "queued", "stage": "", "regenerated_from": old.id})
    return run_dict(new_run, news_title=news_title)
