from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: Optional[str] = None

    class Config:
        from_attributes = True


class AuthResponse(UserOut):
    token: str
    expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
