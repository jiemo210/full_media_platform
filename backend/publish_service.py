"""
全媒体聚合平台 - 发布服务（半自动发布包 + 模拟直发）
====================================================
当前采用双轨制：未接入官方 API 的平台生成一键复制发布包；
“模拟发布”用于联调，真实 API 按资质后续接入。
"""
import re

from config import get_platform, get_platforms
from logger import get_logger

logger = get_logger(__name__)


def get_platform_label(key: str) -> str:
    for p in get_platforms():
        if p.get("key") == key:
            return p.get("label", key)
    return key


def generate_package(title: str, content: str, platform: str) -> str:
    """生成半自动发布复制包：标题 + 正文 + 话题标签"""
    label = get_platform_label(platform)
    topics = []
    for kw in re.split(r"[\s，。、,]+", title)[:3]:
        if len(kw) >= 2:
            topics.append(f"#{kw}")
    body = content.strip()
    if platform == "weibo":
        # 微博优先话题标签
        return f"{' '.join(topics)}\n{title}\n\n{body[:450]}"
    return f"【{label}】{title}\n\n{body}\n\n{' '.join(topics)}"


def create_tasks(db, user_id, title, content, platforms, article_id=None, news_id=None):
    from models import PublishTask
    tasks = []
    for platform in platforms:
        task = PublishTask(
            article_id=article_id,
            news_id=news_id,
            platform=platform,
            title=title,
            content=content,
            status="pending",
            package_text=generate_package(title, content, platform),
            created_by=user_id,
        )
        db.add(task)
        tasks.append(task)
    db.commit()
    for t in tasks:
        db.refresh(t)
    logger.info(f"[publish] 用户 {user_id} 创建 {len(tasks)} 个发布任务")
    return tasks


def mock_publish(db, task):
    """发布跳转：标记为 jumped（已跳转平台，等待用户确认实际发布）。"""
    task.status = "jumped"
    task.external_url = get_platform(task.platform).get("jump_url", "") or f"https://{task.platform}.example.com"
    db.commit()
    return task


def confirm_publish(db, task):
    """用户确认已在平台发布：jumped -> published。"""
    from datetime import datetime
    task.status = "published"
    task.published_at = datetime.utcnow()
    db.commit()
    return task
