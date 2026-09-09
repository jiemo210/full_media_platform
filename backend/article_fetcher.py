"""全媒体聚合平台 - 新闻正文抓取"""
import re

import requests
from bs4 import BeautifulSoup

from logger import get_logger

logger = get_logger(__name__)


def fetch_article(url: str, fallback_text: str = "") -> dict:
    """抓取新闻正文，返回 {text, cover_image}；失败时用摘要兜底。"""
    if not url:
        return {"text": fallback_text, "cover_image": ""}
    try:
        resp = requests.get(
            url, timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        paras = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 20]
        text = "\n".join(dict.fromkeys(paras))[:5000]
        img = soup.find("img")
        cover = img.get("src") or img.get("data-src") or "" if img else ""
        return {"text": text or fallback_text, "cover_image": cover}
    except Exception as e:
        logger.warning(f"正文抓取失败 {url}: {e}")
        return {"text": fallback_text, "cover_image": ""}
