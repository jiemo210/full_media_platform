"""全媒体聚合平台 - 短篇小说路由（创作 / 本地小说库 / AI 大纲总结 / 发布）"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session
from typing import Optional

from config import get as cfg_get
from database import SessionLocal, get_db
from deps import get_token_payload, require_editor
from models import NovelChapter, NovelProject
from novel_service import (
    build_reference_text, chapter_count_for_length, generate_chapter_content,
    generate_outline, generate_settings, generate_summary,
)
from publish_service import create_tasks
from rate_limit import check_limit, record_hit
from logger import get_logger
from schemas import (
    ChapterGenerateRequest, ChapterUpdate, NovelCreate, NovelImport,
    NovelPublishRequest, NovelUpdate, OutlineRequest,
)

router = APIRouter(prefix="/api/novels", tags=["短篇小说"])
logger = get_logger(__name__)


def _check_ai_rate(user: dict):
    limit = cfg_get("AI_RATE_LIMIT", 50)
    window = cfg_get("AI_RATE_WINDOW", 1) * 3600
    key = f"ai:rate:{user.get('user_id')}"
    if check_limit(key, limit, window, 1):
        raise HTTPException(status_code=429, detail=f"AI 调用过于频繁：{window // 3600} 小时内最多 {limit} 次")
    record_hit(key, window, 1)


def _wc(text: str) -> int:
    return len((text or "").replace("\n", "").replace(" ", ""))


def _project_dict(p: NovelProject, with_chapters=False) -> dict:
    data = {
        "id": p.id, "title": p.title, "genre": p.genre, "length_target": p.length_target,
        "style": p.style, "synopsis": p.synopsis or "", "world_setting": p.world_setting or "",
        "characters": p.characters or [], "outline": p.outline or [], "summary": p.summary or {},
        "reference_ids": p.reference_ids or [], "in_library": p.in_library,
        "status": p.status, "word_count": p.word_count or 0,
        "user_id": p.user_id, "created_at": p.created_at, "updated_at": p.updated_at,
    }
    if with_chapters:
        data["chapters"] = [_chapter_dict(c) for c in sorted(p.chapters, key=lambda c: c.chapter_number)]
    return data


def _chapter_dict(c: NovelChapter) -> dict:
    return {
        "id": c.id, "chapter_number": c.chapter_number, "title": c.title or "",
        "content": c.content or "", "word_count": c.word_count or 0,
        "outline": c.outline or "", "status": c.status, "updated_at": c.updated_at,
    }


def _get_project_or_404(db: Session, project_id: int, user: dict) -> NovelProject:
    p = db.query(NovelProject).filter(NovelProject.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="小说不存在")
    if not p.in_library and p.user_id != user.get("user_id"):
        raise HTTPException(status_code=403, detail="无权访问该小说")
    return p


def _recalc_project_words(db: Session, p: NovelProject):
    p.word_count = sum((c.word_count or 0) for c in p.chapters)
    db.commit()


@router.get("")
def list_novels(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    genre: Optional[str] = None,
    library: Optional[bool] = None,
    user: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    query = db.query(NovelProject)
    if library:
        query = query.filter(NovelProject.in_library.is_(True))
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(NovelProject.title.like(like))
    if genre:
        query = query.filter(NovelProject.genre == genre)
    total = query.count()
    rows = query.order_by(desc(NovelProject.updated_at)).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_project_dict(p) for p in rows], "total": total, "page": page, "page_size": page_size}


@router.post("")
def create_novel(req: NovelCreate, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="标题不能为空")
    p = NovelProject(
        title=req.title.strip(), genre=req.genre, length_target=req.length_target,
        style=req.style, synopsis=req.synopsis, reference_ids=req.reference_ids,
        in_library=req.in_library, status="draft", user_id=user.get("user_id"),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _project_dict(p)


@router.post("/import")
def import_novel(req: NovelImport, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """本地导入小说：按 800-1500 字切片生成章节，默认入库。"""
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="正文不能为空")
    p = NovelProject(
        title=req.title.strip(), genre=req.genre, status="imported",
        in_library=req.in_library, user_id=user.get("user_id"),
    )
    db.add(p)
    db.flush()
    # 按段落聚合切片
    paras = [x.strip() for x in content.replace("\r", "").split("\n") if x.strip()]
    chunks, buf = [], ""
    for para in paras:
        if len(buf) + len(para) > 1500 and buf:
            chunks.append(buf)
            buf = ""
        buf += para + "\n"
    if buf:
        chunks.append(buf)
    for i, chunk in enumerate(chunks, 1):
        db.add(NovelChapter(
            project_id=p.id, chapter_number=i, title=f"第{i}章",
            content=chunk.strip(), word_count=_wc(chunk), status="imported",
        ))
    db.commit()
    _recalc_project_words(db, p)
    db.refresh(p)
    return _project_dict(p)


@router.get("/{project_id}")
def novel_detail(project_id: int, user: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    p = _get_project_or_404(db, project_id, user)
    return _project_dict(p, with_chapters=True)


@router.put("/{project_id}")
def update_novel(project_id: int, req: NovelUpdate, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    p = _get_project_or_404(db, project_id, user)
    for k, v in req.dict(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _project_dict(p)


@router.delete("/{project_id}")
def delete_novel(project_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    p = _get_project_or_404(db, project_id, user)
    db.delete(p)
    db.commit()
    return {"message": "小说已删除"}


@router.post("/{project_id}/summary")
def novel_summary(project_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """AI 大纲总结：人物介绍 / 情节大纲 / 题材分类。"""
    _check_ai_rate(user)
    p = _get_project_or_404(db, project_id, user)
    result = generate_summary(p)
    # 题材以用户设定为准，AI 分类仅存入 summary，不覆盖
    p.summary = result
    db.commit()
    db.refresh(p)
    return {"message": "大纲总结已生成", "summary": result}


@router.post("/{project_id}/outline/generate")
def novel_outline(project_id: int, req: OutlineRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """生成分章大纲，并按大纲创建章节骨架。"""
    _check_ai_rate(user)
    p = _get_project_or_404(db, project_id, user)
    ref_text = build_reference_text(db, p.reference_ids or [])
    count = req.chapter_count or chapter_count_for_length(p.length_target or 30000)
    outline = generate_outline(
        p.title, p.genre, p.synopsis or "", p.world_setting or "",
        p.characters or [], count, ref_text,
    )
    if not outline:
        raise HTTPException(status_code=500, detail="大纲生成失败，请重试")
    p.outline = outline
    p.status = "outline"
    # 建章节骨架（已存在的同号章节更新标题/要点，不重复创建）
    existing = {c.chapter_number: c for c in p.chapters}
    for item in outline:
        num = item.get("chapter", 0)
        if num in existing:
            existing[num].title = item.get("title", f"第{num}章")
            existing[num].outline = "；".join(item.get("points", []))
        else:
            db.add(NovelChapter(
                project_id=p.id, chapter_number=num,
                title=item.get("title", f"第{num}章"),
                outline="；".join(item.get("points", [])),
            ))
    db.commit()
    db.refresh(p)
    return {"message": f"大纲已生成（{len(outline)} 章）", "outline": outline}


@router.post("/{project_id}/settings/generate")
def novel_settings(project_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """生成设定：梗概 / 世界观 / 角色卡。"""
    _check_ai_rate(user)
    p = _get_project_or_404(db, project_id, user)
    ref_text = build_reference_text(db, p.reference_ids or [])
    result = generate_settings(p.title, p.genre, p.style, p.length_target or 30000, "", ref_text)
    p.synopsis = result.get("synopsis", p.synopsis or "")
    p.world_setting = result.get("world_setting", p.world_setting or "")
    p.characters = result.get("characters", p.characters or [])
    p.status = "setting"
    db.commit()
    db.refresh(p)
    return {"message": "设定已生成", "settings": result}


# ---------- 章节 ----------

@router.get("/{project_id}/chapters")
def list_chapters(project_id: int, user: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    p = _get_project_or_404(db, project_id, user)
    return {"items": [_chapter_dict(c) for c in sorted(p.chapters, key=lambda c: c.chapter_number)]}


@router.post("/{project_id}/chapters")
def add_chapter(project_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    p = _get_project_or_404(db, project_id, user)
    num = max([c.chapter_number for c in p.chapters], default=0) + 1
    c = NovelChapter(project_id=p.id, chapter_number=num, title=f"第{num}章")
    db.add(c)
    db.commit()
    db.refresh(c)
    return _chapter_dict(c)


@router.get("/{project_id}/chapters/{chapter_id}")
def chapter_detail(project_id: int, chapter_id: int, user: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    _get_project_or_404(db, project_id, user)
    c = db.query(NovelChapter).filter(NovelChapter.id == chapter_id, NovelChapter.project_id == project_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="章节不存在")
    return _chapter_dict(c)


@router.put("/{project_id}/chapters/{chapter_id}")
def update_chapter(project_id: int, chapter_id: int, req: ChapterUpdate, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    p = _get_project_or_404(db, project_id, user)
    c = db.query(NovelChapter).filter(NovelChapter.id == chapter_id, NovelChapter.project_id == project_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="章节不存在")
    for k, v in req.dict(exclude_unset=True).items():
        setattr(c, k, v)
    if req.content is not None or req.title is not None:
        c.word_count = _wc(c.content)
    db.commit()
    _recalc_project_words(db, p)
    db.refresh(c)
    return _chapter_dict(c)


@router.delete("/{project_id}/chapters/{chapter_id}")
def delete_chapter(project_id: int, chapter_id: int, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    p = _get_project_or_404(db, project_id, user)
    c = db.query(NovelChapter).filter(NovelChapter.id == chapter_id, NovelChapter.project_id == project_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="章节不存在")
    db.delete(c)
    db.commit()
    _recalc_project_words(db, p)
    return {"message": "章节已删除"}


@router.post("/{project_id}/chapters/{chapter_id}/generate")
def generate_chapter(project_id: int, chapter_id: int, req: ChapterGenerateRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """AI 生成章节正文（SSE 流式，生成完成后自动落库）。"""
    _check_ai_rate(user)
    db.close()
    db = SessionLocal()
    p = db.query(NovelProject).filter(NovelProject.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="小说不存在")
    c = db.query(NovelChapter).filter(NovelChapter.id == chapter_id, NovelChapter.project_id == project_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="章节不存在")
    if req.regenerate:
        c.content = ""
        db.commit()
    prev = "；".join(
        f"第{x.chapter_number}章：{(x.content or '')[:300]}"
        for x in sorted(p.chapters, key=lambda x: x.chapter_number)
        if x.id != c.id and x.content
    )

    def event_stream():
        buf = ""
        try:
            for token in generate_chapter_content(p, c, req.model, prev[:2000]):
                buf += token
                yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
            # 落库
            local_db = SessionLocal()
            try:
                row = local_db.query(NovelChapter).filter(NovelChapter.id == c.id).first()
                proj = local_db.query(NovelProject).filter(NovelProject.id == p.id).first()
                if row and proj:
                    row.content = buf.strip()
                    row.word_count = _wc(buf)
                    row.status = "generated"
                    proj.status = "writing" if proj.status not in ("completed", "imported") else proj.status
                    proj.word_count = sum((x.word_count or 0) for x in proj.chapters)
                    local_db.commit()
            finally:
                local_db.close()
            yield f"data: {json.dumps({'type': 'done', 'word_count': _wc(buf)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{project_id}/generate-all")
def generate_all(project_id: int, req: ChapterGenerateRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """一键生成全部章节：逐章流式生成并自动落库（自动分章，已有正文的章节跳过）。"""
    _check_ai_rate(user)
    p = _get_project_or_404(db, project_id, user)
    chapters = sorted(p.chapters, key=lambda c: c.chapter_number)
    if not chapters:
        raise HTTPException(status_code=400, detail="暂无章节，请先生成大纲")
    db.close()
    target_words = max(800, round((p.length_target or 30000) / len(chapters)))
    rate_key = f"ai:rate:{user.get('user_id')}"
    rate_limit = cfg_get("AI_RATE_LIMIT", 50)
    rate_window = cfg_get("AI_RATE_WINDOW", 1) * 3600

    def event_stream():
        prev = ""
        total_wc = 0
        generated = 0
        try:
            for idx, c in enumerate(chapters):
                if c.content and c.status == "generated":
                    yield f"data: {json.dumps({'type': 'chapter_skip', 'chapter': c.chapter_number, 'title': c.title}, ensure_ascii=False)}\n\n"
                    continue
                if check_limit(rate_key, rate_limit, rate_window, 1):
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI 调用次数已达上限，已生成的章节已保存'}, ensure_ascii=False)}\n\n"
                    return
                record_hit(rate_key, rate_window, 1)
                yield f"data: {json.dumps({'type': 'chapter_start', 'chapter': c.chapter_number, 'title': c.title, 'index': idx + 1, 'total': len(chapters)}, ensure_ascii=False)}\n\n"
                buf = ""
                try:
                    for token in generate_chapter_content(p, c, req.model, prev, target_words):
                        buf += token
                        yield f"data: {json.dumps({'type': 'token', 'chapter': c.chapter_number, 'content': token}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.warning(f"[novel] 第{c.chapter_number}章生成失败: {e}")
                    yield f"data: {json.dumps({'type': 'chapter_error', 'chapter': c.chapter_number, 'message': str(e)}, ensure_ascii=False)}\n\n"
                    break
                local_db = SessionLocal()
                try:
                    row = local_db.query(NovelChapter).filter(NovelChapter.id == c.id).first()
                    proj = local_db.query(NovelProject).filter(NovelProject.id == p.id).first()
                    if row and proj:
                        row.content = buf.strip()
                        row.word_count = _wc(buf)
                        row.status = "generated"
                        if proj.status not in ("completed", "imported"):
                            proj.status = "writing"
                        proj.word_count = sum((x.word_count or 0) for x in proj.chapters)
                        local_db.commit()
                finally:
                    local_db.close()
                wc = _wc(buf)
                total_wc += wc
                generated += 1
                prev = f"第{c.chapter_number}章《{c.title}》：{buf[:400]}"
                yield f"data: {json.dumps({'type': 'chapter_done', 'chapter': c.chapter_number, 'word_count': wc}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'total_word_count': total_wc, 'generated': generated, 'chapters': len(chapters)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.warning(f"[novel] 一键生成异常: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{project_id}/publish")
def publish_novel(project_id: int, req: NovelPublishRequest, user: dict = Depends(require_editor), db: Session = Depends(get_db)):
    """整本小说转发布任务（复用发布中台）。"""
    p = _get_project_or_404(db, project_id, user)
    if not req.platforms:
        raise HTTPException(status_code=400, detail="请至少选择一个发布平台")
    content = "\n\n".join(
        f"## 第{c.chapter_number}章 {c.title}\n\n{c.content}"
        for c in sorted(p.chapters, key=lambda x: x.chapter_number) if c.content
    )
    if not content.strip():
        raise HTTPException(status_code=400, detail="小说正文为空，请先生成章节")
    tasks = create_tasks(db, user.get("user_id"), p.title, content, req.platforms)
    return {"message": f"已创建 {len(tasks)} 个发布任务", "tasks": [{"id": t.id, "platform": t.platform} for t in tasks]}
