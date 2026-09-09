"""全媒体聚合平台 - 数据模型"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), default="admin")  # admin / editor / viewer
    nickname = Column(String(50), default="")
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)  # 首次登录强制改密
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    articles = relationship("Article", back_populates="creator")


class News(Base):
    """热点新闻"""
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False, index=True)
    title_hash = Column(String(64), default="", index=True)  # 去重哈希（批量查重）
    summary = Column(Text, default="")
    source = Column(String(50), nullable=False, index=True)      # 来源 key
    source_name = Column(String(50), default="")                 # 来源显示名
    url = Column(Text, default="")
    image_url = Column(String(500), default="")
    heat_score = Column(Float, default=0)
    rank = Column(Integer, default=0)                            # 源内排名
    category = Column(String(30), default="综合")                # 板块/分类
    published_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    articles = relationship("Article", back_populates="news")


class Article(Base):
    """AI 生成文章（改写或创作）"""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    news_id = Column(Integer, ForeignKey("news.id"), nullable=True)
    title = Column(String(300), nullable=False)
    content_md = Column(Text().with_variant(LONGTEXT, "mysql"), default="")       # Markdown 原文（含 base64 图片）
    content_html = Column(Text().with_variant(LONGTEXT, "mysql"), default="")     # 富文本 HTML（编辑器使用）
    source_type = Column(String(20), default="rewrite")  # rewrite / create
    style = Column(String(50), default="专业深度")
    platform = Column(String(50), default="")   # 生成时面向的平台
    status = Column(String(20), default="draft")  # draft / published
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", back_populates="articles")
    news = relationship("News", back_populates="articles")


class PublishTask(Base):
    """发布任务（简化版：平台 + 复制包）"""
    __tablename__ = "publish_tasks"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    news_id = Column(Integer, nullable=True)
    platform = Column(String(50), nullable=False)
    title = Column(String(500), default="")
    content = Column(Text().with_variant(LONGTEXT, "mysql"), default="")
    status = Column(String(20), default="pending", index=True)  # pending/published/failed
    package_text = Column(Text().with_variant(LONGTEXT, "mysql"), default="")     # 半自动发布复制包
    external_url = Column(String(500), default="")
    fail_reason = Column(String(500), default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)


class MediaAsset(Base):
    """本地素材库"""
    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), default="image")      # image/cover/video_cover
    url = Column(String(500), default="")
    original_name = Column(String(200), default="")
    mime = Column(String(50), default="")
    size = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class NovelProject(Base):
    """短篇小说项目（同时是本地小说库实体）"""
    __tablename__ = "novel_projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    genre = Column(String(50), default="玄幻")
    length_target = Column(Integer, default=30000)
    style = Column(String(50), default="专业深度")
    synopsis = Column(Text, default="")
    world_setting = Column(Text, default="")
    characters = Column(JSON, default=[])      # [{name, identity, personality, role}]
    outline = Column(JSON, default=[])         # [{chapter, title, points: []}]
    summary = Column(JSON, default={})         # {characters, plot{start,develop,climax,end}, genre, tags}
    reference_ids = Column(JSON, default=[])   # 参考作品 id（引用库内大纲总结）
    in_library = Column(Boolean, default=False)
    status = Column(String(20), default="draft")  # draft/setting/outline/writing/completed/imported
    word_count = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chapters = relationship("NovelChapter", back_populates="project", cascade="all, delete-orphan")


class NovelChapter(Base):
    """小说章节"""
    __tablename__ = "novel_chapters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("novel_projects.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(200), default="")
    content = Column(Text().with_variant(LONGTEXT, "mysql"), default="")
    word_count = Column(Integer, default=0)
    outline = Column(Text, default="")
    status = Column(String(20), default="draft")  # draft/generated/edited/finalized
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("NovelProject", back_populates="chapters")


class PipelineRun(Base):
    """一键成稿任务流"""
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_type = Column(String(20), default="rewrite")   # rewrite / create
    news_id = Column(Integer, nullable=True, index=True)
    topic = Column(Text().with_variant(LONGTEXT, "mysql"), default="")
    mode = Column(String(10), default="auto")             # auto / step（step 预留）
    config = Column(JSON, default={})                     # 风格/字数/平台/模型/风控开关/修订轮数/发布平台
    status = Column(String(20), default="queued", index=True)  # queued/running/completed/failed/cancelled
    current_stage = Column(String(30), default="")
    worker_id = Column(String(64), default="")
    ai_calls = Column(Integer, default=0)
    article_id = Column(Integer, nullable=True)
    error = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    artifacts = relationship(
        "PipelineStageArtifact", back_populates="run",
        cascade="all, delete-orphan",
        order_by="PipelineStageArtifact.order_no",
    )


class PipelineStageArtifact(Base):
    """任务流阶段产物"""
    __tablename__ = "pipeline_stage_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(30), nullable=False)            # material/draft/risk/revise/risk_final/finalize
    order_no = Column(Integer, default=0)
    title = Column(String(300), default="")
    content_md = Column(Text().with_variant(LONGTEXT, "mysql"), default="")
    meta = Column(JSON, default={})
    status = Column(String(20), default="running")        # running/done/failed/skipped
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    run = relationship("PipelineRun", back_populates="artifacts")
