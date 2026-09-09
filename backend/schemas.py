"""全媒体聚合平台 - Pydantic 数据模式"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    nickname: str = ""


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class NewsBase(BaseModel):
    id: int
    title: str
    summary: str
    source: str
    source_name: str
    url: str
    image_url: str
    heat_score: float
    rank: int
    category: str
    published_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class NewsListResponse(BaseModel):
    items: List[NewsBase]
    total: int
    page: int
    page_size: int


class CrawlResponse(BaseModel):
    total: int
    new_count: int
    by_source: dict
    skipped: list


class RewriteRequest(BaseModel):
    style: str = "专业深度"
    extra_prompt: str = ""
    platform: str = ""
    model: str = ""
    word_count: int = 800


class CreateRequest(BaseModel):
    topic: str
    style: str = "专业深度"
    word_count: int = 800
    extra_prompt: str = ""
    platform: str = ""
    model: str = ""


class ArticleBase(BaseModel):
    id: int
    news_id: Optional[int]
    title: str
    content_md: str
    content_html: str
    source_type: str
    style: str
    platform: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    items: List[ArticleBase]
    total: int
    page: int
    page_size: int


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content_md: Optional[str] = None
    content_html: Optional[str] = None


class ArticleSaveRequest(BaseModel):
    """编辑器保存（不重新调用 AI）"""
    news_id: Optional[int] = None
    title: str
    content_md: str = ""
    content_html: str = ""
    source_type: str = "rewrite"
    style: str = ""
    platform: str = ""


class SuggestionsRequest(BaseModel):
    """AI 改写建议生成请求"""
    model: str = ""
    count: int = 4


class RiskCheckRequest(BaseModel):
    """AI 风控检查请求"""
    title: str = ""
    content: str = ""
    platform: str = ""


class RiskReviseRequest(BaseModel):
    """按风控建议修改文章请求"""
    title: str = ""
    content: str = ""
    platform: str = ""
    model: str = ""
    issues: List[str] = []
    suggestions: List[str] = []


class MaterialSearchRequest(BaseModel):
    """资料搜索请求"""
    query: str
    days: int = 0  # 时间范围（天）：0=不限，>0 表示仅最近 N 天


class PipelineRunCreate(BaseModel):
    """一键成稿任务创建请求"""
    source_type: str = "rewrite"          # rewrite（热点改写）/ create（自由创作）
    news_id: Optional[int] = None
    topic: str = ""
    style: str = "专业深度"
    word_count: int = 800
    platform: str = ""
    model: str = ""
    mode: str = "auto"                    # auto / step（step 预留）
    auto_fix: bool = True                 # 风控高风险时自动按建议修订
    publish_platforms: List[str] = []     # 完成后自动创建发布任务的平台


class AIModelItem(BaseModel):
    key: str
    name: str
    model: str
    base_url: str = ""
    api_key: str = ""
    enabled: bool = True
    is_default: bool = False


class StyleItem(BaseModel):
    name: str
    description: str = ""


class ConfigUpdate(BaseModel):
    updates: dict


class PublishRequest(BaseModel):
    article_id: Optional[int] = None
    news_id: Optional[int] = None
    title: str
    content: str
    platforms: List[str]


class PublishTaskBase(BaseModel):
    id: int
    platform: str
    title: str
    content: str
    status: str
    package_text: str
    external_url: str
    fail_reason: str
    jump_url: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class PublishTaskUpdate(BaseModel):
    """发布任务编辑"""
    title: Optional[str] = None
    content: Optional[str] = None
    platform: Optional[str] = None


class PublishTaskListResponse(BaseModel):
    items: List[PublishTaskBase]
    total: int
    page: int
    page_size: int


class SourceUpdate(BaseModel):
    sources: dict


class StatsResponse(BaseModel):
    total_news: int
    total_articles: int
    total_publish_tasks: int
    last_crawl_time: Optional[str] = None
    sources: dict


# ============ 短篇小说 ============
class NovelCreate(BaseModel):
    title: str
    genre: str = "玄幻"
    length_target: int = 30000
    style: str = "专业深度"
    synopsis: str = ""
    reference_ids: List[int] = []
    in_library: bool = False


class NovelImport(BaseModel):
    title: str
    genre: str = "玄幻"
    content: str
    in_library: bool = True


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    length_target: Optional[int] = None
    style: Optional[str] = None
    synopsis: Optional[str] = None
    world_setting: Optional[str] = None
    characters: Optional[List[dict]] = None
    in_library: Optional[bool] = None
    status: Optional[str] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    outline: Optional[str] = None
    status: Optional[str] = None


class OutlineRequest(BaseModel):
    chapter_count: Optional[int] = None


class ChapterGenerateRequest(BaseModel):
    model: str = ""
    regenerate: bool = False


class NovelPublishRequest(BaseModel):
    platforms: List[str]
