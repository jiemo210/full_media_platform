"""
全媒体聚合平台 - 短篇小说服务
==============================
设定生成 / 分章大纲 / 逐章正文（流式）/ AI 大纲总结 / 参考作品注入
"""
import json
import re

from ai_service import _chat_stream_with_failover, _chat_with_failover
from logger import get_logger

logger = get_logger(__name__)

GENRES = ["玄幻", "都市", "悬疑", "言情", "科幻", "历史", "武侠", "奇幻", "现实", "其他"]

SYSTEM_SETTING = "你是一个资深小说创作顾问，输出结构清晰、可直接用于创作的设定与大纲。"
SYSTEM_WRITER = "你是一个优秀的中文小说作者，文笔流畅、情节紧凑、人物鲜活。输出内容使用 Markdown 格式，仅正文，不含章节标题。"


def chapter_count_for_length(length: int) -> int:
    if length <= 12000:
        return 12
    if length <= 20000:
        return 20
    if length <= 35000:
        return 30
    return 45


def build_reference_text(db, reference_ids: list) -> str:
    """读取参考作品的 AI 大纲总结，构造参考提示词。"""
    if not reference_ids:
        return ""
    from models import NovelProject
    parts = []
    for rid in reference_ids:
        ref = db.query(NovelProject).filter(NovelProject.id == rid).first()
        if not ref or not ref.summary:
            continue
        s = ref.summary
        text = f"《{ref.title}》（{s.get('genre', ref.genre)}）"
        if s.get("characters"):
            text += "；人物：" + "；".join(f"{c.get('name')}({c.get('identity', '')}-{c.get('personality', '')})" for c in s["characters"][:5])
        plot = s.get("plot") or {}
        if plot:
            text += "；情节：" + " → ".join(str(plot.get(k, "")).strip() for k in ("start", "develop", "climax", "end") if plot.get(k))
        if s.get("tags"):
            text += "；标签：" + "、".join(s["tags"])
        parts.append(text)
    if not parts:
        return ""
    return (
        "可参考以下作品的大纲总结（仅借鉴题材手法、人物设定逻辑与结构节奏，必须原创，不得抄袭原文）：\n"
        + "\n".join(parts)
    )


def generate_settings(title, genre, style, length, topic="", reference_text=""):
    prompt = (
        f"请为小说《{title}》创作设定。\n"
        f"题材：{genre}；写作风格：{style}；目标篇幅：约 {length} 字。\n"
        f"主题方向：{topic or '不限'}。\n"
        f"{reference_text}\n"
        "请输出 JSON（不要多余说明）："
        '{"synopsis":"故事梗概(200字内)","world_setting":"世界观设定(300字内)",'
        '"characters":[{"name":"姓名","identity":"身份","personality":"性格","role":"在故事中的作用"}]}'
        "，角色 4-6 个。"
    )
    content = _chat_with_failover(
        [{"role": "system", "content": SYSTEM_SETTING}, {"role": "user", "content": prompt}],
        temperature=0.8, max_tokens=2000,
    )
    return _parse_json(content) or {"synopsis": "", "world_setting": "", "characters": []}


def generate_outline(title, genre, synopsis, world_setting, characters, chapter_count, reference_text=""):
    chars_text = "\n".join(f"- {c.get('name')}（{c.get('identity', '')}）：{c.get('personality', '')}；作用：{c.get('role', '')}" for c in characters)
    prompt = (
        f"为小说《{title}》生成 {chapter_count} 章的分章大纲。\n题材：{genre}\n"
        f"梗概：{synopsis}\n世界观：{world_setting}\n角色：\n{chars_text}\n"
        f"{reference_text}\n"
        "输出 JSON 数组：[{\"chapter\":1,\"title\":\"章节标题\",\"points\":[\"要点1\",\"要点2\"]},...]，"
        "每章 2-3 个要点，情节要有起承转合与结尾高潮。"
    )
    content = _chat_with_failover(
        [{"role": "system", "content": SYSTEM_SETTING}, {"role": "user", "content": prompt}],
        temperature=0.8, max_tokens=4000,
    )
    outline = _parse_json(content)
    if not isinstance(outline, list):
        outline = []
    # 规范化
    for i, item in enumerate(outline):
        item["chapter"] = i + 1
        item.setdefault("title", f"第{i + 1}章")
        item.setdefault("points", [])
    return outline


def _chapter_prompt(project, chapter, prev_summary="", target_words=1200):
    chars_text = "\n".join(f"- {c.get('name')}（{c.get('identity', '')}）：{c.get('personality', '')}；作用：{c.get('role', '')}" for c in project.characters)
    outline_summary = "；".join(f"第{o.get('chapter')}章《{o.get('title')}》{'/'.join(o.get('points', []))}" for o in (project.outline or [])[:60])
    return (
        f"小说《{project.title}》（{project.genre}，风格 {project.style}）。\n"
        f"世界观：{project.world_setting}\n角色：\n{chars_text}\n"
        f"全书大纲：{outline_summary}\n"
        f"前文摘要：{prev_summary or '本文是第一章'}\n"
        f"本章：第{chapter.chapter_number}章《{chapter.title}》，本章要点：{chapter.outline or '（承接大纲）'}\n"
        f"请撰写本章正文，约 {target_words} 字，Markdown 格式（可用 ## 小节、- 列表），只输出正文。"
    )


def generate_chapter_content(project, chapter, model="", prev_summary="", target_words=1200):
    return _chat_stream_with_failover(
        [{"role": "system", "content": SYSTEM_WRITER}, {"role": "user", "content": _chapter_prompt(project, chapter, prev_summary, target_words)}],
        temperature=0.85, max_tokens=4000, preferred=model,
    )


def generate_summary(project):
    """AI 大纲总结：人物介绍 / 情节大纲 / 题材分类。"""
    chapters = sorted(project.chapters, key=lambda c: c.chapter_number)
    body = "\n".join(
        f"第{c.chapter_number}章《{c.title}》：{(c.content or '')[:600]}"
        for c in chapters if c.content
    )
    if not body:
        body = project.synopsis or "（正文为空）"
    prompt = (
        f"请对小说《{project.title}》（题材：{project.genre}）做大纲总结。\n正文摘要：\n{body[:8000]}\n"
        "输出 JSON："
        '{"characters":[{"name":"姓名","identity":"身份","personality":"性格","role":"作用"}],'
        '"plot":{"start":"开端","develop":"发展","climax":"高潮","end":"结局"},'
        '"genre":"主题材(从 玄幻/都市/悬疑/言情/科幻/历史/武侠/奇幻/现实 选)","tags":["标签1","标签2"]}'
    )
    content = _chat_with_failover(
        [{"role": "system", "content": "你是资深文学编辑，输出精炼的总结 JSON。"}, {"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=2500,
    )
    return _parse_json(content) or {"characters": [], "plot": {}, "genre": project.genre, "tags": []}


def _parse_json(content):
    """从模型输出中提取 JSON。"""
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.M)
    stripped = text.lstrip()
    try:
        # 数组优先（大纲等多对象输出）
        if stripped.startswith("["):
            start = text.find("[")
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "[":
                    depth += 1
                elif text[i] == "]":
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[start:i + 1])
        start = text.find("{")
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[start:i + 1])
        return json.loads(text)
    except Exception:
        # 尝试数组
        try:
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
        except Exception:
            pass
        logger.warning(f"[novel] JSON 解析失败: {text[:120]}")
        return None
