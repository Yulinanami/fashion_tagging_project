from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DB_URL

Base = declarative_base()


def _ensure_database_exists():
    url = make_url(DB_URL)
    database = url.database
    if not database:
        return
    # MySQL 需要连接到已存在的库才能执行 CREATE DATABASE，这里连接到 mysql 系统库
    root_url = url.set(database="mysql")
    root_engine = create_engine(root_url)
    with root_engine.connect() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    root_engine.dispose()


_ensure_database_exists()

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def init_db():
    # Import models inside to avoid circular imports
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns():
    # 自检 users 表字段，不存在则补列（兼容不支持 IF NOT EXISTS 的 MySQL 版本）
    desired = {
        "token_expires_at": "DATETIME",
        "refresh_token": "VARCHAR(255)",
        "refresh_expires_at": "DATETIME",
    }
    with engine.begin() as conn:
        existing = set()
        try:
            rows = conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME='users' AND TABLE_SCHEMA=DATABASE()"
                )
            )
            existing = {row[0] for row in rows}
        except Exception:
            existing = set()

        for col, ddl in desired.items():
            if col in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
            except Exception:
                # 如果失败（权限/版本），继续启动；此时需手动迁移
                pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
