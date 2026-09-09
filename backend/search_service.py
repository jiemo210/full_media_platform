"""资料搜索服务：360/Bing 网页检索（仅新闻文章）+ AI 扩词/精选（本地热点库在路由层合并）。"""
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from ai_service import _chat_with_failover
from logger import get_logger

logger = get_logger(__name__)

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
}

# 明显非新闻/文章类的域名片段（百科、词典、问答、视频、电商等）
_NON_NEWS_HOST_SUBSTRINGS = (
    "baike.baidu", "baike.sogou", "hanyuguoxue", "hgcha", "zdic", "cidian",
    "dict.youdao", "iciba", "zhihu.com", "douban.com", "taobao.com", "jd.com",
    "bilibili.com", "youku.com", "iqiyi.com", "youtube.com", "ximalaya.com",
    "weibo.com", "xiaohongshu", "qq.com/weather", "amap.com",
)
_ARTICLE_LIKE_PATH = re.compile(
    r"(/\d{4}[/\-\.]\d{1,2}|/\d{5,}|/\d+\.html$|/\d+\.jhtml$|"
    r"/(news|article|detail|story|content|a|n)/|(^|\.)news\.|/\d{8}/)",
    re.I,
)
_DATE_HINT = re.compile(r"(20\d{2})[年\-/\.](\d{1,2})[月\-/\.](\d{1,2})")
_NON_NEWS_TITLE_HINTS = (
    "百度百科", "词典", "字典", "的意思", "释义", "拼音", "汉语汉字",
    "英汉", "翻译", "成语", "百科", "词汇", "近义词",
)


def is_news_article(title: str, url: str) -> bool:
    """启发式判断是否为新闻/文章（排除百科、词典、问答、视频、首页、论坛等）。"""
    t = (title or "").strip()
    if any(h in t for h in _NON_NEWS_TITLE_HINTS):
        return False
    low_url = (url or "").lower()
    if not low_url or low_url.startswith(("mailto:", "javascript:")):
        return False
    # 搜索引擎跳转链接（so.com/link 等）：无法读取目标路径，仅按标题判断
    if "so.com/link" in low_url or "link?m=" in low_url:
        return len(t) >= 8
    for h in _NON_NEWS_HOST_SUBSTRINGS:
        if h in low_url:
            return False
    # 去掉协议与参数，取路径部分
    rest = low_url.split("//", 1)[-1] if "//" in low_url else low_url
    host = rest.split("/", 1)[0]
    path = rest.split("/", 1)[1] if "/" in rest else ""
    path = path.split("?", 1)[0].split("#", 1)[0]
    if re.search(r"/(s|search|video|v|play|question|forum|thread|job|mall|list|user|topic|zhuanlan)/", path):
        return False
    if path.endswith((".mp4", ".mp3", ".jpg", ".png", ".pdf")):
        return False
    # 首页/频道根路径（无文章特征则剔除）
    if not path or path in ("index.html", "index.jhtml", "index.php"):
        return "news" in host or host.endswith(".gov.cn")
    # 有文章特征的 URL（日期/数字 ID/news 域名等）直接保留
    if _ARTICLE_LIKE_PATH.search(low_url):
        return True
    # 无特征且路径过短的视为非文章
    if len(path) < 12:
        return False
    return True


def item_date(item: dict):
    """从摘要/标题中提取日期（如 2026年8月18日 / 2026-08-18），无则返回 None。"""
    for text in (item.get("snippet", "") or "", item.get("title", "") or ""):
        m = _DATE_HINT.search(text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
    return None


def filter_by_recency(items: list, days: int) -> list:
    """时间过滤：显式日期早于窗口的剔除；无日期信息的保留（交由 AI 时间判断）。"""
    if not days or days <= 0:
        return items
    cutoff = date.today() - timedelta(days=days)
    out = []
    for it in items:
        d = item_date(it)
        if d is None or d >= cutoff:
            out.append(it)
    return out


def so_search(query: str, limit: int = 8) -> list:
    """360 网页搜索（中文新闻相关性较好），失败返回空列表。"""
    try:
        resp = requests.get("https://www.so.com/s", params={"q": query}, timeout=12, headers=_UA)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for li in soup.select("li.res-list"):
            h3 = li.find("h3")
            a = h3.find("a", href=True) if h3 else li.find("a", href=True)
            if not a:
                continue
            title = (a.get_text(strip=True) or "").strip()
            url = (a.get("href") or "").strip()
            if not title or not url or len(title) < 8 or title.endswith("相关新闻"):
                continue
            desc_el = li.select_one("p.res-desc") or li.select_one("p[class*=desc]")
            desc = desc_el.get_text(strip=True) if desc_el else ""
            cite = li.select_one("cite") or li.select_one("span[class*=site]")
            source = cite.get_text(strip=True) if cite else _domain_label(url)
            items.append({"title": title[:200], "url": url, "snippet": desc[:400], "source": source})
            if len(items) >= limit:
                break
        return items
    except Exception as e:
        logger.warning(f"[search] 360 检索失败: {e}")
        return []


def bing_search(query: str, limit: int = 8) -> list:
    """Bing RSS 检索，返回 [{title, url, snippet, source}]；失败返回空列表。"""
    try:
        resp = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "format": "rss", "count": str(min(limit, 15))},
            timeout=12, headers=_UA,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = []
        for it in root.findall(".//item")[:limit]:
            title = (it.findtext("title") or "").strip()
            url = (it.findtext("link") or "").strip()
            desc = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
            if not title or not url:
                continue
            source = _domain_label(url)
            items.append({"title": title[:200], "url": url, "snippet": desc[:400], "source": source})
        return items
    except Exception as e:
        logger.warning(f"[search] Bing 检索失败: {e}")
        return []


def web_search(query: str, limit: int = 8) -> list:
    """网页检索：优先 360（中文质量好），失败回退 Bing RSS。"""
    items = so_search(query, limit)
    if items:
        return items
    return bing_search(query, limit)


def _domain_label(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url or "")
    if not m:
        return ""
    host = m.group(1).lower().replace("www.", "")
    known = {
        "baidu.com": "百度", "sina.com.cn": "新浪", "qq.com": "腾讯", "sohu.com": "搜狐",
        "163.com": "网易", "thepaper.cn": "澎湃新闻", "people.com.cn": "人民网",
        "xinhuanet.com": "新华网", "news.cn": "新华网", "gov.cn": "政府网",
        "zhihu.com": "知乎", "bilibili.com": "B站", "weibo.com": "微博",
        "dahe.cn": "大河网", "zynews.cn": "中原网", "hntv.tv": "大象新闻",
    }
    for k, v in known.items():
        if host == k or host.endswith("." + k):
            return v
    return host


def _extract_json(content: str):
    text = (content or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.M)
    start = text.find("[")
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
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def ai_expand_queries(user_input: str) -> list:
    """AI 将用户输入扩展为 1-3 个中文检索词；失败时回退为原文。"""
    try:
        content = _chat_with_failover([
            {"role": "system", "content": "你是新闻检索策划助手。将用户输入拆解为适合检索新闻/热点资料的中文关键词或短语，每个不超过 20 字。只输出 JSON 数组，如 [\"关键词1\", \"关键词2\", \"关键词3\"]，1-3 个。"},
            {"role": "user", "content": user_input},
        ], temperature=0.4, max_tokens=300)
        queries = _extract_json(content)
        if isinstance(queries, list):
            cleaned = [str(q).strip()[:30] for q in queries if str(q).strip()]
            if cleaned:
                return cleaned[:3]
    except Exception as e:
        logger.warning(f"[search] AI 扩词失败: {e}")
    return [user_input.strip()[:50]] if user_input.strip() else []


def ai_refine(query: str, items: list, days: int = 0) -> dict:
    """AI 精选：综合摘要 + 相关/热点标注 + 延伸搜索词（按需限时/限新闻）。失败时返回空结构。"""
    if not items:
        return {"summary": "", "picks": [], "related_queries": []}
    lines = []
    for i, it in enumerate(items):
        src = it.get("source") or it.get("source_name") or ""
        lines.append(f"[{i}] {it.get('title', '')}（{src}）{it.get('snippet', '')[:120]}")
    try:
        time_tip = f"时间要求：仅保留最近 {days} 天内的新闻/文章；结果无时间信息时，按发布日期判断，过于陈旧（超过 {days} 天）的不要入选。" if days > 0 else ""
        content = _chat_with_failover([
            {"role": "system", "content": (
                "你是资料搜集与热点研判助手。针对用户主题，分析检索到的资料，输出 JSON："
                '{"summary": "80字以内综合摘要", "picks": [{"index": 数字(从0开始), "reason": "一句话说明相关性", "is_hot": true/false}], '
                '"related_queries": ["延伸搜索词1", "延伸搜索词2", "延伸搜索词3"]}。'
                "picks 从列表挑选 3-6 条与主题最相关的新闻/文章内容；"
                "仅保留新闻、文章、报告类条目，排除百科词条、词典、问答、视频、网站首页等非文章内容；"
                "无法判断热点时 is_hot 取 false。"
            )},
            {"role": "user", "content": f"用户主题/输入：{query}\n{time_tip}\n\n检索结果列表：\n" + "\n".join(lines[:30])},
        ], temperature=0.3, max_tokens=1500)
        obj = _extract_json(content)
        if not obj:
            obj = {}
        picks = obj.get("picks") or []
        valid = [p for p in picks if isinstance(p.get("index"), int) and 0 <= p["index"] < len(items)]
        return {
            "summary": str(obj.get("summary") or "").strip(),
            "picks": valid[:8],
            "related_queries": [str(q).strip()[:30] for q in (obj.get("related_queries") or []) if str(q).strip()][:5],
        }
    except Exception as e:
        logger.warning(f"[search] AI 精选失败: {e}")
        return {"summary": "", "picks": [], "related_queries": []}
