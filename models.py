from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    token = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
