"""全媒体聚合平台 - 数据库模块（MySQL 优先，SQLite 兜底）"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import get_db_url
from logger import get_logger

logger = get_logger(__name__)


def _mask_db_url(url: str) -> str:
    """日志脱敏：不打印数据库口令。"""
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" in rest:
        userinfo, host = rest.rsplit("@", 1)
        if ":" in userinfo:
            user, _pw = userinfo.split(":", 1)
            userinfo = f"{user}:***"
        rest = f"{userinfo}@{host}"
    return f"{scheme}://{rest}"


DATABASE_URL = get_db_url()
logger.info(f"数据库连接: {_mask_db_url(DATABASE_URL)}")
_is_mysql = DATABASE_URL.startswith("mysql")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if not _is_mysql else {"charset": "utf8mb4"},
    pool_pre_ping=_is_mysql,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
