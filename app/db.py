from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DB_URL
from app.seed_data import ensure_outfits_seeded

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
    _seed()


def _seed():
    with SessionLocal() as db:
        ensure_outfits_seeded(db)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
