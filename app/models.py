from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # 存储明文密码（已按需求取消 hash）
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Outfit(Base):
    __tablename__ = "outfits"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    image_url = Column(String(512), nullable=True)
    gender = Column(String(50), nullable=False, default="unisex")
    style = Column(String(100), nullable=True)
    season = Column(String(100), nullable=True)
    scene = Column(String(100), nullable=True)
    weather = Column(String(100), nullable=True)
    tags = Column(Text, nullable=True)  # JSON 字符串
    is_user_upload = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "outfit_id", name="uq_user_outfit"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    outfit_id = Column(
        Integer, ForeignKey("outfits.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow)
