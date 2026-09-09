"""轻量级数据库迁移（无第三方依赖）

替代每次启动执行裸 ALTER：使用 schema_migrations 表记录已应用版本，
新增字段/索引以迁移条目形式追加，幂等且不阻塞启动。
"""
import hashlib

from sqlalchemy import text

from database import engine
from logger import get_logger

logger = get_logger(__name__)
_IS_MYSQL = engine.url.drivername.startswith("mysql")


def _columns(conn, table: str) -> set:
    if _IS_MYSQL:
        rows = conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
        ), {"t": table}).fetchall()
    else:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {str(r[1]) for r in rows}
    return {str(r[0]) for r in rows}


def _indexes(conn, table: str) -> set:
    if _IS_MYSQL:
        rows = conn.execute(text("SHOW INDEX FROM news")).fetchall()
        return {str(r[2]) for r in rows}
    rows = conn.execute(text("PRAGMA index_list(news)")).fetchall()
    return {str(r[1]) for r in rows}


def m_news_title_hash(conn):
    """news.title_hash 列 + 非唯一索引（存量重复标题不阻塞），供批量去重。"""
    cols = _columns(conn, "news")
    if "title_hash" not in cols:
        if _IS_MYSQL:
            conn.execute(text("ALTER TABLE news ADD COLUMN title_hash VARCHAR(64) NULL"))
        else:
            conn.execute(text("ALTER TABLE news ADD COLUMN title_hash VARCHAR(64)"))
    rows = conn.execute(text(
        "SELECT id, title FROM news WHERE title_hash IS NULL OR title_hash = ''"
    )).fetchall()
    for rid, title in rows:
        h = hashlib.sha1((title or "").encode("utf-8")).hexdigest()
        conn.execute(text("UPDATE news SET title_hash = :h WHERE id = :id"), {"h": h, "id": rid})
    if "ix_news_title_hash" not in _indexes(conn, "news"):
        conn.execute(text("CREATE INDEX ix_news_title_hash ON news (title_hash)"))


def m_users_must_change_password(conn):
    """users.must_change_password：存量默认口令账号强制改密。"""
    cols = _columns(conn, "users")
    if "must_change_password" not in cols:
        if _IS_MYSQL:
            conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0"))
        else:
            conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 0"))


def m_news_fulltext(conn):
    """中文搜索 FULLTEXT 索引（MySQL ngram，尽力而为；失败自动回退 LIKE）。"""
    if not _IS_MYSQL:
        return
    if "ft_news_title_summary" in _indexes(conn, "news"):
        return
    try:
        conn.execute(text(
            "ALTER TABLE news ADD FULLTEXT INDEX ft_news_title_summary (title, summary) WITH PARSER ngram"
        ))
        logger.info("[migration] 已创建 FULLTEXT 索引 ft_news_title_summary")
    except Exception as e:
        logger.warning(f"[migration] FULLTEXT 索引创建失败（回退 LIKE 搜索）: {e}")


def m_pipeline_tables(conn):
    """一键成稿任务表：由启动时 create_all 负责建表，此处仅校验并记录版本。"""
    for table in ("pipeline_runs", "pipeline_stage_artifacts"):
        cols = _columns(conn, table)
        if not cols:
            logger.warning(f"[migration] {table} 不存在（create_all 未执行？）")


def m_pipeline_topic_longtext(conn):
    """pipeline_runs.topic 扩容（支持整段素材/长主题输入）。"""
    if _IS_MYSQL and "topic" in _columns(conn, "pipeline_runs"):
        conn.execute(text("ALTER TABLE pipeline_runs MODIFY COLUMN topic LONGTEXT NULL"))


MIGRATIONS = [
    {
        "id": "m001_longtext_fields",
        "sqls": {
            "mysql": [
                "ALTER TABLE articles MODIFY COLUMN content_md LONGTEXT, MODIFY COLUMN content_html LONGTEXT",
                "ALTER TABLE publish_tasks MODIFY COLUMN content LONGTEXT, MODIFY COLUMN package_text LONGTEXT",
            ],
            "sqlite": [],
        },
    },
    {"id": "m002_news_title_hash", "fn": m_news_title_hash},
    {"id": "m003_users_must_change_password", "fn": m_users_must_change_password},
    {"id": "m004_news_fulltext", "fn": m_news_fulltext, "best_effort": True},
    {"id": "m005_pipeline_tables", "fn": m_pipeline_tables},
    {"id": "m006_pipeline_topic_longtext", "fn": m_pipeline_topic_longtext},
]


def ensure_migrations():
    """按序应用未执行的迁移；单条失败仅告警，不阻塞启动。"""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " id VARCHAR(100) PRIMARY KEY,"
            " applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        ))
    applied = {r[0] for r in engine.connect().execute(text("SELECT id FROM schema_migrations"))}
    for m in MIGRATIONS:
        if m["id"] in applied:
            continue
        try:
            with engine.begin() as conn:
                if m.get("fn"):
                    m["fn"](conn)
                for sql in (m.get("sqls") or {}).get("mysql" if _IS_MYSQL else "sqlite", []):
                    conn.execute(text(sql))
                conn.execute(text("INSERT INTO schema_migrations (id) VALUES (:id)"), {"id": m["id"]})
            logger.info(f"[migration] 已应用 {m['id']}")
        except Exception as e:
            if m.get("best_effort"):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO schema_migrations (id) VALUES (:id)"), {"id": m["id"]})
                except Exception:
                    pass
                logger.warning(f"[migration] {m['id']} 尽力而为失败（已跳过，不再重试）: {e}")
            else:
                logger.warning(f"[migration] {m['id']} 失败（跳过，不阻塞启动）: {e}")
