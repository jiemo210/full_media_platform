"""
全媒体聚合平台 - AI 服务
========================
基于 OpenAI 兼容接口（DeepSeek），提供：
- 热点新闻 AI 改写（流式/同步）
- 自定义主题 AI 创作（流式/同步）
- Markdown → HTML 转换（富文本编辑器展示）
"""
import json
import re

import requests

from config import get as cfg_get, get_ai_models, get_platforms, is_ai_available
from logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "你是一个资深自媒体内容创作助手。输出内容必须使用 Markdown 格式："
    "一级标题只用 1 个（文章标题），正文使用 ## 分节、- 列表、**强调**、> 引用、``` 代码块。"
    "内容观点客观，信息密度高，适合发布到中文内容平台。"
)


def get_ai_model(model_key=None) -> dict:
    """解析模型配置：按 key 匹配 AI_MODELS；未指定时返回默认模型。"""
    models = get_ai_models()
    if model_key:
        for m in models:
            if m.get("key") == model_key and m.get("enabled", True):
                return m
    for m in models:
        if m.get("is_default") and m.get("enabled", True):
            return m
    if models:
        return models[0]
    return {"key": "", "name": "默认", "model": cfg_get("AI_MODEL", "deepseek-chat"), "base_url": "", "api_key": ""}


def _headers(api_key=""):
    return {
        "Authorization": f"Bearer {api_key or cfg_get('AI_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def _chat_url(base_url=""):
    base = (base_url or cfg_get("AI_BASE_URL", "https://api.deepseek.com")).rstrip("/")
    return f"{base}/chat/completions"


def _chat(messages, temperature=0.8, max_tokens=4000, model_cfg=None):
    if not is_ai_available():
        raise RuntimeError("AI 服务未配置（请在 .env 设置 FMP_AI_API_KEY）")
    model_cfg = model_cfg or get_ai_model()
    resp = requests.post(
        _chat_url(model_cfg.get("base_url")), headers=_headers(model_cfg.get("api_key")), timeout=180,
        json={
            "model": model_cfg.get("model") or cfg_get("AI_MODEL", "deepseek-chat"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _chat_stream(messages, temperature=0.8, max_tokens=4000, model_cfg=None):
    if not is_ai_available():
        raise RuntimeError("AI 服务未配置（请在 .env 设置 FMP_AI_API_KEY）")
    model_cfg = model_cfg or get_ai_model()
    resp = requests.post(
        _chat_url(model_cfg.get("base_url")), headers=_headers(model_cfg.get("api_key")), timeout=300, stream=True,
        json={
            "model": model_cfg.get("model") or cfg_get("AI_MODEL", "deepseek-chat"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        },
    )
    resp.raise_for_status()
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            break
        try:
            delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
            if delta:
                yield delta
        except (KeyError, json.JSONDecodeError):
            continue


def _iter_models(preferred=None):
    """启用的模型列表，首选模型排最前（用于失败自动切换）。"""
    models = [m for m in get_ai_models() if m.get("enabled", True)]
    if preferred:
        models = [m for m in models if m.get("key") == preferred] + [m for m in models if m.get("key") != preferred]
    return models or [get_ai_model()]


def _chat_with_failover(messages, temperature=0.8, max_tokens=4000, preferred=None):
    """同步调用：首选模型失败自动切换下一个启用模型。"""
    last_err = None
    for model_cfg in _iter_models(preferred):
        try:
            return _chat(messages, temperature, max_tokens, model_cfg=model_cfg)
        except Exception as e:
            last_err = e
            logger.warning(f"[ai] 模型 {model_cfg.get('key')} 调用失败，尝试下一个: {e}")
    raise last_err or RuntimeError("所有 AI 模型调用失败")


def _chat_stream_with_failover(messages, temperature=0.8, max_tokens=4000, preferred=None):
    """流式调用：在首个 token 前自动切换失败模型。"""
    last_err = None
    for model_cfg in _iter_models(preferred):
        try:
            gen = _chat_stream(messages, temperature, max_tokens, model_cfg=model_cfg)
            first = next(gen)
            def chain():
                yield first
                yield from gen
            return chain()
        except StopIteration:
            return iter(())
        except Exception as e:
            last_err = e
            logger.warning(f"[ai] 流式模型 {model_cfg.get('key')} 启动失败，尝试下一个: {e}")
    raise last_err or RuntimeError("所有 AI 模型调用失败")


def _parse_title(content: str, fallback: str) -> str:
    m = re.match(r"^#\s+(.+)$", content.strip(), re.M)
    if m:
        return m.group(1).strip()
    return fallback


def _strip_title_from_content(content: str) -> str:
    lines = content.strip().splitlines()
    if lines and re.match(r"^#\s+", lines[0]):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _platform_tip(platform):
    """平台提示词：含平台名称与规范性要求（按 key 或 label 匹配）。"""
    if not platform:
        return ""
    cfg = {}
    for p in get_platforms():
        if p.get("key") == platform or p.get("label") == platform:
            cfg = p
            break
    tip = f"目标发布平台：{cfg.get('label', platform)}，请按该平台风格调整。"
    if cfg.get("rules"):
        tip += f"\n平台规范性要求：{cfg['rules']}（务必遵守）"
    return tip


# ---------- 热点新闻 AI 改写 ----------
def rewrite_prompt(title, summary, original_text, style, extra_prompt, platform, word_count=800):
    platform_tip = _platform_tip(platform)
    return (
        f"请根据以下热点新闻改写一篇深度文章。\n"
        f"改写风格：{style}\n目标字数：约 {word_count} 字\n{platform_tip}\n补充要求：{extra_prompt or '无'}\n\n"
        f"新闻标题：{title}\n新闻摘要：{summary}\n新闻正文：\n{original_text[:4000]}"
    )


def generate_rewrite(title, summary, original_text, style="专业深度", extra_prompt="", platform="", model=None, word_count=800):
    content = _chat_with_failover([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": rewrite_prompt(title, summary, original_text, style, extra_prompt, platform, word_count)},
    ], preferred=model)
    return {"title": _parse_title(content, title), "content": _strip_title_from_content(content)}


def generate_rewrite_stream(title, summary, original_text, style="专业深度", extra_prompt="", platform="", model=None, word_count=800):
    return _chat_stream_with_failover([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": rewrite_prompt(title, summary, original_text, style, extra_prompt, platform, word_count)},
    ], preferred=model)


def generate_rewrite_suggestions(title, summary, model=None, count=4):
    """生成 AI 改写建议（供用户勾选带入补充提示词）。"""
    model_cfg = get_ai_model(model)
    prompt = (
        f"请针对以下热点新闻，给出 {count} 条文章改写建议。每条建议一句话、具体可执行，"
        f"不要编号外的说明，直接输出，每条一行。\n新闻标题：{title}\n新闻摘要：{summary}"
    )
    content = _chat_with_failover([
        {"role": "system", "content": "你是一个资深编辑，输出精炼、可直接执行的改写建议，每条一行。"},
        {"role": "user", "content": prompt},
    ], temperature=0.6, max_tokens=800, preferred=model)
    lines = []
    for ln in content.splitlines():
        ln = re.sub(r"^\s*(?:\d+[.、)）]|[-\u2022•])\s*", "", ln).strip()
        if ln:
            lines.append(ln)
    return [ln for ln in lines if 8 <= len(ln) <= 120][:count] or [
        "开头用一句吸睛导语直接点明事件核心",
        "突出最新进展与关键数据，提升信息密度",
        "补充事件背景与影响分析，增强深度",
        "结尾给出观点或后续关注点，引导互动",
    ]


# ---------- 自定义主题 AI 创作 ----------
def create_prompt(topic, style, word_count, extra_prompt, platform):
    platform_tip = _platform_tip(platform)
    return (
        f"请以「{topic}」为主题创作一篇约 {word_count} 字的文章。\n"
        f"创作风格：{style}\n{platform_tip}\n补充要求：{extra_prompt or '无'}\n\n"
        "要求：第一行用 Markdown 一级标题给出文章标题，正文用 ## 分节。"
    )


def generate_create(topic, style="专业深度", word_count=800, extra_prompt="", platform="", model=None):
    content = _chat_with_failover([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": create_prompt(topic, style, word_count, extra_prompt, platform)},
    ], preferred=model)
    return {
        "title": _parse_title(content, topic),
        "content": _strip_title_from_content(content),
        "topic": topic,
    }


def generate_create_stream(topic, style="专业深度", word_count=800, extra_prompt="", platform="", model=None):
    return _chat_stream_with_failover([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": create_prompt(topic, style, word_count, extra_prompt, platform)},
    ], preferred=model)


# ---------- AI 风控检查 ----------
RISK_SYSTEM_PROMPT = (
    "你是一个内容安全与平台风控审核专家。请对文章标题与正文做合规与风控审查："
    "1) 是否违反中国法律法规、社会主义核心价值观、公序良俗；"
    "2) 是否含虚假/不实信息、低俗、暴力、歧视、医疗或金融违规宣传、侵权抄袭等风险；"
    "3) 是否违反所选平台的规范性/风控要求。"
    "只输出一个 JSON 对象（不要多余文字）："
    '{"pass": true/false, "level": "low|medium|high", '
    '"issues": ["风险点1", ...], "suggestions": ["修改建议1", ...]}。'
    "level 定义：low=无风险可直接发布；medium=存在需修改点，修改后可发布；high=存在违规风险，不建议发布。"
    "issues 为空数组表示无风险；请给出具体、可执行的修改建议。"
)


def _extract_json(content: str):
    """从模型输出中提取第一个 JSON 对象。"""
    text = (content or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.M)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    try:
        return json.loads(text)
    except Exception:
        return None


def risk_check_content(title: str, content: str, platform: str = "", extra: str = "") -> dict:
    """AI 风控检查：合规 + 平台风控要求，返回 {pass, level, issues, suggestions}。"""
    cfg = {}
    if platform:
        for p in get_platforms():
            if p.get("key") == platform or p.get("label") == platform:
                cfg = p
                break
    platform_tip = ""
    if platform:
        platform_tip = f"目标平台：{cfg.get('label', platform)}。"
        rules = cfg.get("risk_rules") or cfg.get("rules") or ""
        if rules:
            platform_tip += f"平台风控/规范性要求：{rules}（请重点核查正文是否违反）。"
    user_prompt = f"文章标题：{title or '（无）'}\n\n正文：\n{(content or '')[:6000]}\n\n{platform_tip}"
    if extra:
        user_prompt += f"\n补充风控要求：{extra}"
    result = _chat_with_failover(
        [
            {"role": "system", "content": RISK_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2, max_tokens=1500,
    )
    data = _extract_json(result) or {}
    return {
        "pass": bool(data.get("pass", False)),
        "level": str(data.get("level", "medium") if data else "unknown"),
        "issues": list(data.get("issues") or []) if data else ["风控检查解析失败，请重试"],
        "suggestions": list(data.get("suggestions") or []) if data else [],
    }


# ---------- 按风控建议修改（AI 润色改进） ----------
RISK_REVISE_SYSTEM_PROMPT = (
    "你是一个资深自媒体内容创作与风控修改专家。请根据给出的风控审核结果修改文章："
    "1) 消除全部风险点，严格遵守法律法规、社会主义核心价值观、公序良俗与平台规范；"
    "2) 保留原文核心信息、结构与写作风格，不得无依据编造事实或删除必要信息；"
    "3) 完整输出修改后的文章：第一行用 Markdown 一级标题（# ）给出标题，正文用 ## 分节，"
    "直接输出正文内容，不要输出任何解释或前缀。"
)


def build_risk_revise_prompt(title: str, content: str, platform: str = "",
                             issues: list = None, suggestions: list = None) -> str:
    issues = issues or []
    suggestions = suggestions or []
    parts = []
    if issues:
        parts.append("风控风险点：\n" + "\n".join(f"- {i}" for i in issues))
    if suggestions:
        parts.append("修改建议：\n" + "\n".join(f"- {s}" for s in suggestions))
    platform_tip = _platform_tip(platform)
    if platform_tip:
        parts.append(platform_tip)
    return (
        "\n\n".join(parts)
        + f"\n\n原文标题：{title or '（无）'}\n\n原文正文：\n{(content or '')[:8000]}"
        + "\n\n请根据以上风控风险点与修改建议，输出修改后的完整文章。"
    )


def generate_risk_revise_stream(title: str, content: str, platform: str = "",
                                issues: list = None, suggestions: list = None, model: str = ""):
    """按风控建议流式修改文章（返回与原文相同格式的 Markdown 全文）。"""
    return _chat_stream_with_failover(
        [
            {"role": "system", "content": RISK_REVISE_SYSTEM_PROMPT},
            {"role": "user", "content": build_risk_revise_prompt(title, content, platform, issues, suggestions)},
        ],
        temperature=0.5, max_tokens=4000, preferred=model,
    )


# ---------- Markdown → HTML（富文本编辑器） ----------
def markdown_to_html(md: str) -> str:
    if not md:
        return ""
    lines = md.splitlines()
    html = []
    in_list = False
    in_code = False
    code_buf = []

    def close_list():
        nonlocal in_list
        if in_list:
            html.append("</ul>")
            in_list = False

    def safe_url(url, kind="link"):
        url = (url or "").strip()
        low = url.lower()
        if kind == "image":
            if low.startswith(("http://", "https://", "/media/", "data:image/")):
                return url
            return ""
        if low.startswith(("http://", "https://", "mailto:")):
            return url
        return ""

    def inline(text):
        text = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", lambda m: (
            f'<img src="{safe_url(m.group(2), "image")}" alt="{m.group(1)}" '
            'style="max-width:100%;border-radius:8px;margin:8px 0;" />'
            if safe_url(m.group(2), "image") else m.group(0)
        ), text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", lambda m: (
            f'<a href="{safe_url(m.group(2))}" target="_blank" rel="noopener">'
            f'{m.group(1)}</a>' if safe_url(m.group(2)) else m.group(0)
        ), text)
        return text

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                html.append("<pre><code>" + "\n".join(code_buf) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                close_list()
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue
        if not line.strip():
            close_list()
            continue
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            close_list()
            level = len(m.group(1))
            html.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue
        if re.match(r"^>\s?", line):
            close_list()
            html.append(f"<blockquote>{inline(re.sub(r'^>\s?', '', line))}</blockquote>")
            continue
        if re.match(r"^[-*]\s+", line):
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{inline(re.sub(r'^[-*]\s+', '', line))}</li>")
            continue
        close_list()
        html.append(f"<p>{inline(line)}</p>")
    close_list()
    if in_code:
        html.append("<pre><code>" + "\n".join(code_buf) + "</code></pre>")
    return "\n".join(html)
