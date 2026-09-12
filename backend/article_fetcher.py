"""全媒体聚合平台 - 新闻正文抓取"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from logger import get_logger

logger = get_logger(__name__)


_IMG_SKIP_HINTS = ("logo", "icon", "avatar", "qr", "code", "spacer", "pixel", "blank", "ad_", "banner", "share")


def _collect_images(soup: BeautifulSoup, base_url: str, limit: int = 6) -> list:
    """收集正文图片（绝对化 URL、去重、过滤小图/图标类）。"""
    images, seen = [], set()
    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src") or img.get("data-original") or "").strip()
        if not src and img.get("srcset"):
            src = img.get("srcset").split(",")[0].strip().split(" ")[0]
        if not src or src.startswith("data:"):
            continue
        low = src.lower()
        if any(h in low for h in _IMG_SKIP_HINTS):
            continue
        try:
            w = int(re.sub(r"[^\d]", "", str(img.get("width") or "0")) or 0)
            h = int(re.sub(r"[^\d]", "", str(img.get("height") or "0")) or 0)
        except (TypeError, ValueError):
            w = h = 0
        if (w and w < 200) or (h and h < 150):
            continue
        abs_url = urljoin(base_url, src)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        images.append({"url": abs_url, "alt": (img.get("alt") or "").strip()[:80]})
        if len(images) >= limit:
            break
    return images


def fetch_article(url: str, fallback_text: str = "") -> dict:
    """抓取新闻正文，返回 {text, cover_image, images}；失败时用摘要兜底。"""
    if not url:
        return {"text": fallback_text, "cover_image": "", "images": []}
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
        images = _collect_images(soup, url)
        cover = images[0]["url"] if images else ""
        return {"text": text or fallback_text, "cover_image": cover, "images": images}
    except Exception as e:
        logger.warning(f"正文抓取失败 {url}: {e}")
        return {"text": fallback_text, "cover_image": "", "images": []}
