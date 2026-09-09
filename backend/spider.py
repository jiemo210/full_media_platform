"""
全媒体聚合平台 - 热点新闻爬虫
============================
可用源（2026-09 实测）：
  baidu / toutiao / tencent / cctv / sina_finance / nanfang / people / xinhua
  + dahe（大河网）/ zynews（中原网）/ thepaper（澎湃新闻）/ hntv（大象新闻）/ zhengzhou_fabu（郑州发布·政府新闻）
已移除失效源：weibo / zhihu / 36kr / pengpai / douyin / zhejiang
"""
import random
import re
import time
from datetime import datetime
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup

from config import get as cfg_get, get_news_sources
from logger import get_logger

logger = get_logger(__name__)

CATEGORY_KEYWORDS = {
    "时政": ["习近平", "国务院", "总理", "中央", "部委", "政策", "立法", "两会", "外交", "峰会"],
    "财经": ["经济", "股市", "金融", "银行", "房价", "汽车", "公司", "上市", "融资", "GDP", "央行", "利率", "营收", "财报", "新能源"],
    "科技": ["AI", "人工智能", "芯片", "大模型", "科技", "互联网", "机器人", "航天", "华为", "苹果", "OpenAI", "5G", "量子"],
    "社会": ["事故", "灾害", "救援", "警方", "法院", "民生", "社区", "台风", "暴雨", "疫情", "泥石流", "地震"],
    "国际": ["美国", "俄罗斯", "乌克兰", "欧洲", "日本", "韩国", "朝鲜", "联合国", "以色列", "中东", "欧盟", "全球"],
    "文体": ["电影", "票房", "奥运会", "世界杯", "体育", "明星", "音乐", "综艺", "演出", "赛事"],
}


def classify_category(title: str, summary: str = "") -> str:
    text = title + " " + summary
    best, best_score = "综合", 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best_score:
            best, best_score = cat, score
    return best


def _make_absolute(url: str, base: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return urljoin(base, url)


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    skip = ["首页", "登录", "注册", "客户端", "下载", "更多", "设为主页", "收藏本站"]
    if any(s in title for s in skip):
        return ""
    return title


class NewsSpider:
    """多源热点爬虫（结构参考原热点荟项目）"""

    SOURCES = {
        "baidu": "百度新闻",
        "toutiao": "今日头条",
        "tencent": "腾讯新闻",
        "cctv": "央视网",
        "sina_finance": "新浪财经",
        "nanfang": "南方+",
        "people": "人民网",
        "xinhua": "新华网",
        "dahe": "大河网",
        "zynews": "中原网",
        "thepaper": "澎湃新闻",
        "hntv": "大象新闻",
        "zhengzhou_fabu": "郑州发布",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/json,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.baidu.com/",
        })
        self.last_crawl_time = None

    def fetch(self, url: str, timeout: int = 10) -> str:
        try:
            time.sleep(random.uniform(0.3, 0.8))
            resp = self.session.get(url, timeout=timeout)
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as e:
            logger.warning(f"抓取失败 {url}: {e}")
            return ""

    def _item(self, title, summary, source_key, link, rank, interaction=0, image_url=""):
        title = _clean_title(title)
        if not title:
            return None
        heat = round(100.0 - rank * 6 + min(interaction // 100, 60), 1)
        return {
            "title": title,
            "summary": (summary or title)[:300],
            "source": source_key,
            "source_name": self.SOURCES.get(source_key, source_key),
            "url": link,
            "image_url": image_url or "",
            "heat_score": heat,
            "rank": rank + 1,
            "category": classify_category(title, summary or ""),
        }

    # ---------- 百度新闻 ----------
    def crawl_baidu(self):
        out, url = [], "https://top.baidu.com/board?tab=realtime"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        for idx, item in enumerate(soup.select(".category-wrap_iQLoo .content_1YWBm")[:cfg_get("NEWS_PER_SOURCE", 20)]):
            try:
                title_el = item.select_one(".title_dIF3B") or item.select_one("a")
                title = title_el.get_text(strip=True) if title_el else ""
                link = _make_absolute(title_el.get("href", ""), url) if title_el else ""
                desc_el = item.select_one(".desc_3CTxt") or item.select_one(".intro_1l0fX")
                summary = desc_el.get_text(strip=True) if desc_el else title
                item = self._item(title, summary, "baidu", link, idx)
                if item:
                    out.append(item)
            except Exception:
                continue
        return out

    # ---------- 今日头条 ----------
    def crawl_toutiao(self):
        out = []
        try:
            resp = self.session.get("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc", timeout=10)
            data = resp.json().get("data", [])
            for idx, item in enumerate(data[:cfg_get("NEWS_PER_SOURCE", 20)]):
                title = item.get("Title", "")
                hot = item.get("HotValue", 0)
                try:
                    hot = int(hot)
                except (TypeError, ValueError):
                    hot = 0
                image = ""
                if isinstance(item.get("Image"), dict):
                    image = item["Image"].get("url", "")
                news = self._item(title, title + " - 今日头条热点", "toutiao", item.get("Url", ""), idx, interaction=hot, image_url=image)
                if news:
                    out.append(news)
        except Exception as e:
            logger.warning(f"今日头条失败: {e}")
        return out

    # ---------- 腾讯新闻 ----------
    def crawl_tencent(self):
        out = []
        try:
            resp = self.session.get("https://r.inews.qq.com/gw/event/hot_ranking_list?page_size=50", timeout=10)
            data = resp.json()
            newslist = ((data.get("idlist") or [{}])[0]).get("newslist") or []
            for idx, item in enumerate(newslist):
                if item.get("id", "").startswith("TIP") or item.get("articletype") == "560":
                    continue
                title = item.get("longtitle") or item.get("title", "")
                link = item.get("surl") or f"https://view.inews.qq.com/a/{item.get('id')}"
                news = self._item(title, title, "tencent", link, idx)
                if news:
                    out.append(news)
                if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                    break
        except Exception as e:
            logger.warning(f"腾讯新闻失败: {e}")
        return out

    # ---------- 央视网 ----------
    def crawl_cctv(self):
        out, url = [], "https://news.cctv.com/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        items = soup.select(".title a") or soup.select("a[href*='cctv.com']")
        seen = set()
        for idx, item in enumerate(items[:100]):
            title = _clean_title(item.get_text(strip=True))
            if not title or title in seen or len(title) < 6:
                continue
            seen.add(title)
            link = _make_absolute(item.get("href", ""), url)
            news = self._item(title, title + " - 央视新闻", "cctv", link, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 新浪财经 ----------
    def crawl_sina_finance(self):
        out, url = [], "https://finance.sina.com.cn/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        items = soup.select(".news-item a") or soup.select("a[href*='finance.sina']")
        seen = set()
        for idx, item in enumerate(items[:100]):
            title = _clean_title(item.get_text(strip=True))
            if not title or title in seen or len(title) < 6:
                continue
            seen.add(title)
            link = _make_absolute(item.get("href", ""), url)
            news = self._item(title, title + " - 新浪财经报道", "sina_finance", link, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 南方+ ----------
    def crawl_nanfang(self):
        out, url = [], "https://www.southcn.com/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        items = soup.select("h2 a") or soup.select(".article-item a") or soup.select("a")
        seen = set()
        for idx, item in enumerate(items[:150]):
            title = _clean_title(item.get_text(strip=True))
            if not title or title in seen or len(title) < 8:
                continue
            seen.add(title)
            link = _make_absolute(item.get("href", ""), url)
            news = self._item(title, title + " - 南方+报道", "nanfang", link, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 人民网 ----------
    def crawl_people(self):
        out, url = [], "http://www.people.com.cn/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        seen = set()
        for idx, a in enumerate(soup.find_all("a", href=True)):
            href = _make_absolute(a.get("href", ""), url)
            if "/n1/" not in href:
                continue
            title = _clean_title(a.get_text(strip=True))
            if not title or title in seen or len(title) < 8:
                continue
            seen.add(title)
            news = self._item(title, title + " - 人民网报道", "people", href, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 新华网 ----------
    def crawl_xinhua(self):
        out, url = [], "http://www.news.cn/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        seen = set()
        for idx, a in enumerate(soup.find_all("a", href=True)):
            href = _make_absolute(a.get("href", ""), url)
            if not re.search(r"/\d{8}/[0-9a-f]+/c\.html$", href):
                continue
            title = _clean_title(a.get_text(strip=True))
            if not title or title in seen or len(title) < 8:
                continue
            seen.add(title)
            news = self._item(title, title + " - 新华网报道", "xinhua", href, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 大河网 ----------
    def crawl_dahe(self):
        out, url = [], "https://news.dahe.cn/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = _make_absolute(a.get("href", ""), url)
            if not re.search(r"news\.dahe\.cn/\d{4}/\d{2}-\d{2}/\d+\.html$", href):
                continue
            title = _clean_title(a.get_text(strip=True))
            if not title or title in seen or len(title) < 8:
                continue
            seen.add(title)
            news = self._item(title, title + " - 大河网", "dahe", href, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 中原网 ----------
    def crawl_zynews(self):
        out, url = [], "https://www.zynews.cn/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = _make_absolute(a.get("href", ""), url)
            if not re.search(r"news\.zynews\.cn/[a-z]+/\d{4}/\d{2}/\d{2}/\d+\.html$", href):
                continue
            title = _clean_title(a.get_text(strip=True))
            if not title or title in seen or len(title) < 8:
                continue
            seen.add(title)
            news = self._item(title, title + " - 中原网", "zynews", href, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 澎湃新闻 ----------
    def crawl_thepaper(self):
        out, url = [], "https://www.thepaper.cn/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not re.search(r"/newsDetail_forward_\d+$", href):
                continue
            href = _make_absolute(href, url)
            title = _clean_title(a.get_text(strip=True))
            # 去掉「推荐/头条」等板块前缀
            title = re.sub(r"^(推荐|头条|24小时|热榜)\s*", "", title)
            if not title or title in seen or len(title) < 8:
                continue
            seen.add(title)
            news = self._item(title, title + " - 澎湃新闻", "thepaper", href, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 大象新闻（大象网 hntv.tv） ----------
    def crawl_hntv(self):
        out, url = [], "https://www.hntv.tv/"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/article/" not in href:
                continue
            href = _make_absolute(href, url).split("?")[0]
            # 标题在 h5（部分页面为强标签），摘要在同级 p
            head = a.find(["h1", "h2", "h3", "h4", "h5", "strong"])
            title = _clean_title(head.get_text(strip=True) if head else a.get_text(strip=True))
            if not title or title in seen or len(title) < 8:
                continue
            seen.add(title)
            p = a.find("p")
            summary = p.get_text(strip=True)[:300] if p else (title + " - 大象新闻")
            news = self._item(title, summary, "hntv", href, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    # ---------- 郑州发布（郑州市政府「郑州新闻」频道） ----------
    def crawl_zhengzhou_fabu(self):
        out, url = [], "https://www.zhengzhou.gov.cn/news1/index_35.jhtml"
        soup = BeautifulSoup(self.fetch(url) or "", "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not re.search(r"zhengzhou\.gov\.cn/news1/\d+\.jhtml$", _make_absolute(href, url)):
                continue
            span = a.find("span")
            title = _clean_title(span.get_text(strip=True) if span else a.get("title", ""))
            if not title:
                # 兜底：去掉行尾日期与来源
                title = _clean_title(re.sub(r"\d{4}-\d{2}-\d{2}来源：.*$", "", a.get_text(strip=True)))
            if not title or title in seen or len(title) < 8:
                continue
            seen.add(title)
            ems = a.find_all("em")
            summary = ""
            if len(ems) >= 2:
                summary = f"{ems[0].get_text(strip=True)} {ems[1].get_text(strip=True)}"
            news = self._item(title, summary or title + " - 郑州市政府", "zhengzhou_fabu", href, len(out))
            if news:
                out.append(news)
            if len(out) >= cfg_get("NEWS_PER_SOURCE", 20):
                break
        return out

    def crawl_all(self, only_enabled=True, progress_cb=None) -> dict:
        """抓取全部启用源，返回 {source_key: [items]}"""
        result = {}
        sources = get_news_sources()
        for key, crawler in [
            ("baidu", self.crawl_baidu), ("toutiao", self.crawl_toutiao),
            ("tencent", self.crawl_tencent), ("cctv", self.crawl_cctv),
            ("sina_finance", self.crawl_sina_finance), ("nanfang", self.crawl_nanfang),
            ("people", self.crawl_people), ("xinhua", self.crawl_xinhua),
            ("dahe", self.crawl_dahe), ("zynews", self.crawl_zynews),
            ("thepaper", self.crawl_thepaper), ("hntv", self.crawl_hntv),
            ("zhengzhou_fabu", self.crawl_zhengzhou_fabu),
        ]:
            if only_enabled and not sources.get(key, {}).get("enabled", True):
                continue
            try:
                items = crawler()
                result[key] = items
                if progress_cb:
                    progress_cb(key, len(items))
                logger.info(f"[spider] {self.SOURCES[key]} 抓到 {len(items)} 条")
            except Exception as e:
                logger.error(f"[spider] {key} 异常: {e}")
                result[key] = []
        self.last_crawl_time = datetime.now()
        return result

    def health_check(self) -> dict:
        """探测各源可用性（管理后台用）：{key: {ok, count, error}}"""
        result = {}
        for key, crawler in [
            ("baidu", self.crawl_baidu), ("toutiao", self.crawl_toutiao),
            ("tencent", self.crawl_tencent), ("cctv", self.crawl_cctv),
            ("sina_finance", self.crawl_sina_finance), ("nanfang", self.crawl_nanfang),
            ("people", self.crawl_people), ("xinhua", self.crawl_xinhua),
            ("dahe", self.crawl_dahe), ("zynews", self.crawl_zynews),
            ("thepaper", self.crawl_thepaper), ("hntv", self.crawl_hntv),
            ("zhengzhou_fabu", self.crawl_zhengzhou_fabu),
        ]:
            try:
                items = crawler()
                result[key] = {"ok": len(items) > 0, "count": len(items), "error": ""}
            except Exception as e:
                result[key] = {"ok": False, "count": 0, "error": str(e)[:100]}
        return result
