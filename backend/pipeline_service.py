"""一键成稿任务流（M1：自动模式 Worker + DB 状态 + 进程内事件总线）

默认链路：
  rewrite: material -> draft -> risk -> [revise] -> finalize
  create : draft -> risk -> [revise] -> finalize
"""
import json
import re
import threading
import time
from datetime import datetime

from database import SessionLocal
from logger import get_logger
from models import Article, News, PipelineRun, PipelineStageArtifact
from config import get as cfg_get
from rate_limit import check_limit, record_hit

logger = get_logger(__name__)

STAGE_LABELS = {
    "material": "素材收集",
    "draft": "AI 成文",
    "images": "智能配图",
    "risk": "风控检查",
    "revise": "AI 修订",
    "finalize": "入库定稿",
}

_bus_lock = threading.Lock()
_bus = {}          # run_id -> [ {seq,type,payload,ts} ]
_worker_lock = threading.Lock()
_worker = None


class PipelineError(Exception):
    """任务级可预期错误（展示给用户）。"""


def _char_count(text: str) -> int:
    return len((text or "").replace("\n", "").replace(" ", "").replace("\t", ""))


def planned_stages(run: PipelineRun) -> list:
    """任务计划阶段（与执行器保持一致），用于列表进度展示。"""
    cfg = run.config or {}
    stages = []
    if run.source_type == "rewrite":
        stages.append("material")
    stages.append("draft")
    if run.source_type == "rewrite" and cfg_get("PIPELINE_IMAGE_ENABLED", True):
        stages.append("images")
    stages.append("risk")
    if cfg.get("auto_fix", True):
        stages.append("revise")
    stages.append("finalize")
    return stages


# ---------------- 事件总线 ----------------
def publish_event(run_id: int, type_: str, payload: dict = None):
    with _bus_lock:
        seq_list = _bus.setdefault(run_id, [])
        seq = (seq_list[-1]["seq"] + 1) if seq_list else 1
        seq_list.append({
            "seq": seq,
            "type": type_,
            "payload": payload or {},
            "ts": datetime.utcnow().isoformat(),
        })
        # 保留最近 2000 条，防止长任务内存膨胀
        if len(seq_list) > 2000:
            del seq_list[: len(seq_list) - 2000]
        return seq


def events_after(run_id: int, since: int) -> list:
    with _bus_lock:
        seq_list = list(_bus.get(run_id, []))
    return [e for e in seq_list if e["seq"] > since]


# ---------------- 序列化 ----------------
def _artifact_dict(a: PipelineStageArtifact, include_content: bool = False) -> dict:
    d = {
        "id": a.id, "stage": a.stage,
        "stage_label": STAGE_LABELS.get(a.stage, a.stage),
        "order_no": a.order_no, "title": a.title or "",
        "meta": a.meta or {}, "status": a.status,
        "word_count": len((a.content_md or "").replace("\n", "").replace(" ", "")),
        "updated_at": a.updated_at,
    }
    if include_content:
        d["content_md"] = a.content_md or ""
    return d


def run_dict(run: PipelineRun, with_artifacts: bool = False,
             include_content: bool = False, news_title: str = "") -> dict:
    d = {
        "id": run.id, "user_id": run.user_id,
        "source_type": run.source_type, "news_id": run.news_id,
        "topic": run.topic or "", "display_title": news_title or run.topic or "",
        "mode": run.mode, "config": run.config or {},
        "status": run.status, "current_stage": run.current_stage,
        "current_stage_label": STAGE_LABELS.get(run.current_stage, run.current_stage),
        "ai_calls": run.ai_calls or 0, "article_id": run.article_id,
        "error": run.error or "", "created_at": run.created_at,
        "updated_at": run.updated_at, "finished_at": run.finished_at,
    }
    if with_artifacts:
        arts = sorted(run.artifacts, key=lambda x: (x.order_no, x.id))
        d["artifacts"] = [_artifact_dict(a, include_content) for a in arts]
        d["stage_progress"] = {
            "done": sum(1 for a in arts if a.status == "done"),
            "total": sum(1 for a in arts if a.status != "skipped"),
            "labels": [STAGE_LABELS.get(a.stage, a.stage) for a in arts],
        }
    return d


# ---------------- AI 调用封装（限流 + 计数） ----------------
def _ai_guard(db, run: PipelineRun, amount: int = 1):
    limit = cfg_get("AI_RATE_LIMIT", 50)
    window = cfg_get("AI_RATE_WINDOW", 1) * 3600
    key = f"ai:rate:{run.user_id}"
    if check_limit(key, limit, window, amount):
        raise PipelineError(f"AI 调用次数已达上限（{window // 3600} 小时 {limit} 次），任务暂停，请稍后重试")
    record_hit(key, window, amount)
    run.ai_calls = (run.ai_calls or 0) + amount
    db.commit()


def _split_md_title(content: str):
    text = (content or "").strip()
    lines = text.splitlines()
    title = ""
    if lines and re.match(r"^#\s+", lines[0]):
        title = re.sub(r"^#\s+", "", lines[0]).strip()
        lines = lines[1:]
    return title, "\n".join(lines).strip()


# ---------------- 阶段执行 ----------------
def _stage_material(db, run: PipelineRun, art: PipelineStageArtifact):
    news = db.query(News).filter(News.id == run.news_id).first()
    if not news:
        raise PipelineError("新闻不存在或已删除")
    from article_fetcher import fetch_article
    fetched = fetch_article(news.url, news.summary)
    text = (fetched.get("text") or news.summary or news.title or "").strip()
    if not text:
        raise PipelineError("未获取到原文内容")
    images = _localize_images(db, run, fetched.get("images") or [], news.url or "")
    art.title = news.title or ""
    art.content_md = text
    art.meta = {
        "source_name": news.source_name or news.source or "",
        "url": news.url or "",
        "category": news.category or "",
        "heat_score": news.heat_score or 0,
        "fetched": True,
        "images": images,
        "image_count": len(images),
    }
    return text, images


def _localize_images(db, run: PipelineRun, images: list, referer: str = "") -> list:
    """可选：把原文外链图片下载到本地素材库（PIPELINE_DOWNLOAD_IMAGES 开启时）。"""
    if not images:
        return []
    if not cfg_get("PIPELINE_DOWNLOAD_IMAGES", False):
        return [dict(i) for i in images]
    import os
    import uuid
    import requests
    from storage import get_storage
    from models import MediaAsset
    out = []
    for it in images:
        url = (it or {}).get("url") or ""
        if not url.startswith("http"):
            out.append(dict(it))
            continue
        try:
            resp = requests.get(url, timeout=12, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
                "Referer": referer or url,
            })
            resp.raise_for_status()
            ext = os.path.splitext(url.split("?")[0])[1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                ext = ".jpg"
            rel = get_storage().save_bytes(resp.content, f"{uuid.uuid4().hex}{ext}", "images")
            local = get_storage().url_for(rel)
            db.add(MediaAsset(type="image", url=local, original_name=os.path.basename(url)[:100],
                              mime=resp.headers.get("Content-Type", ""), size=len(resp.content),
                              created_by=run.user_id))
            db.commit()
            item = dict(it)
            item["origin_url"] = url
            item["url"] = local
            out.append(item)
        except Exception as e:
            logger.warning(f"[pipeline] 图片本地化失败，保留外链 {url}: {e}")
            out.append(dict(it))
    return out


_IMG_PLACEHOLDER = re.compile(r"\[\[\s*IMG\s*[::]\s*(.*?)\s*\]\]", re.I)


def _fallback_positions(lines: list, count: int) -> list:
    """无占位符时的插入位置：优先各 H2 标题之后，否则按 1/3、2/3 段落。"""
    heads = [i for i, ln in enumerate(lines) if ln.strip().startswith("## ")]
    if len(heads) >= 2:
        return [h + 1 for h in heads[:count]]
    if len(heads) == 1:
        return [heads[0] + 1]
    body = [i for i, ln in enumerate(lines) if ln.strip()]
    if not body:
        return []
    picks = []
    if count >= 1:
        picks.append(body[len(body) // 3])
    if count >= 2 and len(body) > 3:
        picks.append(body[(len(body) * 2) // 3])
    if count >= 3 and len(body) > 6:
        picks.append(body[len(body) // 2])
    return picks


def _stage_images(db, run: PipelineRun, art: PipelineStageArtifact,
                  content: str, images: list):
    """智能配图：优先替换 AI 输出的 [[IMG: 描述]] 占位符，其次按规则兜底插入。"""
    enabled = bool(cfg_get("PIPELINE_IMAGE_ENABLED", True))
    max_n = max(0, int(cfg_get("PIPELINE_IMAGE_MAX", 3) or 0))
    pool = [i for i in (images or []) if (i or {}).get("url")]
    art.meta = {"enabled": enabled, "pool_size": len(pool), "max": max_n}
    if not content:
        return content
    if not enabled or not pool or max_n == 0:
        art.content_md = _IMG_PLACEHOLDER.sub("", content).strip()
        art.meta["inserted"] = 0
        return art.content_md
    used, cursor = [], 0

    def take():
        nonlocal cursor
        while cursor < len(pool):
            img = pool[cursor]
            cursor += 1
            if img["url"] not in [u["url"] for u in used]:
                return img
        return None

    def repl(m):
        img = take()
        if not img:
            return ""
        used.append(img)
        alt = (img.get("alt") or m.group(1) or "配图").strip()[:60]
        return f"![{alt}]({img['url']})"

    content = _IMG_PLACEHOLDER.sub(repl, content)
    content = _IMG_PLACEHOLDER.sub("", content)
    if not used:
        lines = content.split("\n")
        for pos in sorted(_fallback_positions(lines, min(max_n, len(pool))), reverse=True):
            img = take()
            if not img:
                break
            alt = (img.get("alt") or "配图")[:60]
            lines[pos:pos] = ["", f"![{alt}]({img['url']})", ""]
            used.append(img)
        content = "\n".join(lines)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    art.content_md = content
    art.meta["inserted"] = len(used)
    art.meta["used"] = [
        {"url": u.get("url", ""), "alt": u.get("alt", ""), "origin_url": u.get("origin_url", "")}
        for u in used
    ]
    logger.info(f"[pipeline] 任务 {run.id} 智能配图完成，使用 {len(used)} 张（图片池 {len(pool)} 张）")
    return content


def _stage_draft(db, run: PipelineRun, art: PipelineStageArtifact, material_text: str, with_images: bool = False):
    from ai_service import generate_create, generate_rewrite
    cfg = run.config or {}
    style = cfg.get("style") or "专业深度"
    word_count = int(cfg.get("word_count") or 800)
    platform = cfg.get("platform") or ""
    model = cfg.get("model") or ""
    extra_prompt = cfg.get("extra_prompt") or ""
    if run.source_type == "rewrite":
        news = db.query(News).filter(News.id == run.news_id).first()
        if not news:
            raise PipelineError("新闻不存在或已删除")
        result = generate_rewrite(
            news.title, news.summary or "", material_text or news.summary or news.title,
            style, extra_prompt, platform, model, word_count, with_images,
        )
    else:
        if not run.topic.strip():
            raise PipelineError("创作主题不能为空")
        result = generate_create(run.topic, style, word_count, extra_prompt, platform, model, with_images)
    art.title = (result.get("title") or "").strip()
    art.content_md = (result.get("content") or "").strip()
    art.meta["style"] = style
    art.meta["word_count_target"] = word_count
    art.meta["platform"] = platform
    if not art.content_md:
        raise PipelineError("AI 未生成正文，请重试")
    # 长文完整性：不足目标字数 80% 时自动续写（最多 2 轮）
    attempts = 0
    while _char_count(art.content_md) < int(word_count * 0.8) and attempts < 2:
        from ai_service import continue_content
        _ai_guard(db, run)
        extra = (continue_content(art.title or run.topic or "文章", art.content_md,
                                  style, platform, model, word_count) or "").strip()
        if not extra:
            break
        art.content_md = f"{art.content_md.rstrip()}\n\n{extra}"
        attempts += 1
        logger.info(f"[pipeline] 任务 {run.id} 触发续写第 {attempts} 轮，当前字数 {_char_count(art.content_md)}")
    if _char_count(art.content_md) < int(word_count * 0.6):
        logger.warning(f"[pipeline] 任务 {run.id} 生成内容偏短：{_char_count(art.content_md)} 字（目标 {word_count}）")
    return art.content_md


def _stage_risk(db, run: PipelineRun, art: PipelineStageArtifact, title: str, content: str):
    from ai_service import risk_check_content
    if not cfg_get("RISK_CHECK_ENABLED", True):
        art.meta = {"enabled": False, "level": "skipped", "issues": [], "suggestions": []}
        return {"enabled": False, "level": "skipped", "issues": [], "suggestions": []}
    try:
        result = risk_check_content(
            title, content, (run.config or {}).get("platform") or "",
            cfg_get("RISK_CHECK_EXTRA", ""),
        )
    except Exception as e:
        # 风控检查失败不阻断成稿：记录问题并继续入库
        logger.warning(f"[pipeline] 任务 {run.id} 风控检查执行失败（继续流程）: {e}")
        result = {
            "pass": False,
            "level": "unknown",
            "issues": [f"风控检查未完成：{str(e)[:100]}"],
            "suggestions": [],
        }
    art.meta = {"enabled": True, **result}
    return result


def _stage_revise(db, run: PipelineRun, art: PipelineStageArtifact,
                  title: str, content: str, issues: list, suggestions: list):
    from ai_service import generate_risk_revise_stream
    cfg = run.config or {}
    stream = generate_risk_revise_stream(
        title, content, cfg.get("platform") or "",
        issues or [], suggestions or [], cfg.get("model") or "",
    )
    buf = "".join(stream)
    new_title, new_content = _split_md_title(buf)
    if not new_content.strip():
        raise PipelineError("AI 修订未产出有效内容，请重试")
    # 修订不应让篇幅显著缩水，必要时续写补回
    if _char_count(new_content) < _char_count(content) * 0.8:
        from ai_service import continue_content
        _ai_guard(db, run)
        extra = (continue_content(new_title or title, new_content, cfg.get("style") or "专业深度",
                                  cfg.get("platform") or "", cfg.get("model") or "",
                                  int(cfg.get("word_count") or 800)) or "").strip()
        if extra:
            new_content = f"{new_content.rstrip()}\n\n{extra}"
            logger.info(f"[pipeline] 任务 {run.id} 修订后篇幅不足，已续写补回至 {_char_count(new_content)} 字")
            art.meta["continued"] = True
    art.title = new_title or title
    art.content_md = new_content
    art.meta["fixed"] = True
    return art.title, new_content


def _stage_finalize(db, run: PipelineRun, title: str, content: str):
    from ai_service import markdown_to_html
    from publish_service import create_tasks
    cfg = run.config or {}
    article = Article(
        news_id=run.news_id if run.source_type == "rewrite" else None,
        title=title or run.topic or "未命名文章",
        content_md=content,
        content_html=markdown_to_html(content),
        source_type=run.source_type,
        style=cfg.get("style") or "专业深度",
        platform=cfg.get("platform") or "",
        status="draft",
        user_id=run.user_id,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    run.article_id = article.id
    platforms = [p for p in (cfg.get("publish_platforms") or []) if p]
    if platforms:
        try:
            create_tasks(db, run.user_id, article.title, content, platforms,
                         article_id=article.id,
                         news_id=article.news_id if article.news_id else None)
            db.refresh(run)
        except Exception as e:
            logger.warning(f"[pipeline] 发布任务创建失败（文章已保存）: {e}")
    return article


# ---------------- 任务执行 ----------------
def _execute_run(run_id: int):
    db = SessionLocal()
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        db.close()
        return
    if run.status != "running":
        db.close()
        return
    publish_event(run_id, "run_status", {"status": "running", "stage": ""})
    cfg = run.config or {}
    order = 0
    latest_title, latest_content = "", ""
    material_images = []
    risk_result = None
    image_mode = run.source_type == "rewrite" and bool(cfg_get("PIPELINE_IMAGE_ENABLED", True))
    cancelled = False
    try:
        # 阶段规划：material(rewrite) -> draft -> risk -> [revise] -> finalize
        plan = []
        if run.source_type == "rewrite":
            plan.append("material")
        plan.append("draft")
        if image_mode:
            plan.append("images")
        plan += ["risk"]
        if cfg.get("auto_fix", True):
            plan.append("revise")
        plan.append("finalize")

        for stage in plan:
            db.refresh(run)
            if run.status == "cancelled":
                cancelled = True
                break
            run.current_stage = stage
            db.commit()
            publish_event(run_id, "stage_start", {"stage": stage, "label": STAGE_LABELS.get(stage, stage)})
            stage_start = time.time()
            logger.info(f"[pipeline] 任务 {run_id} 开始阶段 {stage}（{STAGE_LABELS.get(stage, stage)}）")
            art = PipelineStageArtifact(run_id=run.id, stage=stage, order_no=order, status="running")
            db.add(art)
            db.commit()
            db.refresh(art)
            order += 1
            try:
                if stage == "material":
                    latest_content, material_images = _stage_material(db, run, art)
                    latest_title = art.title
                elif stage == "draft":
                    _ai_guard(db, run)
                    latest_content = _stage_draft(db, run, art, latest_content, with_images=image_mode)
                    latest_title = art.title
                elif stage == "images":
                    latest_content = _stage_images(db, run, art, latest_content, material_images)
                elif stage == "risk":
                    _ai_guard(db, run)
                    risk_result = _stage_risk(db, run, art, latest_title, latest_content)
                elif stage == "revise":
                    need_fix = bool(
                        risk_result
                        and risk_result.get("enabled") is not False
                        and risk_result.get("pass") is False
                        and risk_result.get("level") in ("medium", "high")
                        and (risk_result.get("issues") or risk_result.get("suggestions"))
                    )
                    if need_fix and latest_content:
                        _ai_guard(db, run)
                        issues = risk_result.get("issues") or []
                        suggestions = risk_result.get("suggestions") or []
                        latest_title, latest_content = _stage_revise(
                            db, run, art, latest_title, latest_content, issues, suggestions,
                        )
                    else:
                        art.status = "skipped"
                        db.commit()
                        publish_event(run_id, "stage_skip", {"stage": stage, "label": STAGE_LABELS.get(stage, stage)})
                        continue
                elif stage == "finalize":
                    target = int(cfg.get("word_count") or 0)
                    if target and _char_count(latest_content) < int(target * 0.6):
                        from ai_service import continue_content
                        _ai_guard(db, run)
                        extra = (continue_content(latest_title or run.topic or "文章", latest_content,
                                                  cfg.get("style") or "专业深度", cfg.get("platform") or "",
                                                  cfg.get("model") or "", target) or "").strip()
                        if extra:
                            latest_content = f"{latest_content.rstrip()}\n\n{extra}"
                            logger.info(f"[pipeline] 任务 {run.id} 定稿前补写，当前 {_char_count(latest_content)} 字（目标 {target}）")
                    article = _stage_finalize(db, run, latest_title, latest_content)
                    art.title = article.title
                    art.content_md = article.content_md
                    art.meta["article_id"] = article.id
            except PipelineError as pe:
                art.meta["error"] = str(pe)
                db.commit()
                raise
            art.status = "done"
            db.commit()
            db.refresh(art)
            publish_event(run_id, "stage_done", {
                "stage": stage,
                "label": STAGE_LABELS.get(stage, stage),
                "word_count": len((art.content_md or "").replace("\n", "").replace(" ", "")),
            })
            logger.info(
                f"[pipeline] 任务 {run_id} 阶段 {stage} 完成，用时 {time.time() - stage_start:.1f}s，"
                f"字数 {len((art.content_md or '').replace(chr(10), '').replace(' ', ''))}"
            )

        if cancelled:
            run.status = "cancelled"
            run.finished_at = datetime.utcnow()
            run.error = "任务已取消"
        else:
            run.status = "completed"
            run.current_stage = ""
            run.finished_at = datetime.utcnow()
        db.commit()
        logger.info(f"[pipeline] 任务 {run_id} 结束，状态={run.status}，AI 调用 {run.ai_calls or 0} 次，文章ID={run.article_id}")
        publish_event(run_id, "run_status", {
            "status": run.status, "article_id": run.article_id,
            "error": run.error or "",
        })
    except PipelineError as e:
        run.status = "failed"
        run.error = str(e)[:500]
        run.finished_at = datetime.utcnow()
        db.commit()
        publish_event(run_id, "run_status", {"status": "failed", "error": str(e)[:500]})
    except Exception as e:
        logger.exception(f"[pipeline] 任务 {run_id} 执行异常")
        run.status = "failed"
        run.error = f"执行异常：{str(e)[:300]}"
        run.finished_at = datetime.utcnow()
        db.commit()
        publish_event(run_id, "run_status", {"status": "failed", "error": run.error})
    finally:
        db.close()


def _claim_next() -> int:
    db = SessionLocal()
    try:
        row = db.query(PipelineRun).filter(PipelineRun.status == "queued").order_by(PipelineRun.id).first()
        if not row:
            return 0
        row.status = "running"
        row.worker_id = "local-worker"
        db.commit()
        return row.id
    finally:
        db.close()


def recover_interrupted():
    """启动时恢复：把遗留 running 任务放回队列（单实例场景）。"""
    db = SessionLocal()
    try:
        db.query(PipelineRun).filter(PipelineRun.status == "running").update({
            "status": "queued",
            "worker_id": "",
            "error": "检测到服务重启，任务已重新排队",
        })
        db.commit()
    finally:
        db.close()


def ensure_worker_started():
    global _worker
    with _worker_lock:
        if _worker and _worker.is_alive():
            return
        _worker = threading.Thread(target=_worker_loop, daemon=True, name="pipeline-worker")
        _worker.start()


def _worker_loop():
    while True:
        run_id = _claim_next()
        if not run_id:
            break
        logger.info(f"[pipeline] 开始执行任务 {run_id}")
        _execute_run(run_id)
