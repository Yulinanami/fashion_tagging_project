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


class WeatherNow(BaseModel):
    temp: Optional[str] = None
    text: Optional[str] = None
    feels_like: Optional[str] = None
    wind_dir: Optional[str] = None
    wind_scale: Optional[str] = None
    humidity: Optional[str] = None
    icon: Optional[str] = None


class WeatherResponse(BaseModel):
    city: str
    location_id: str
    update_time: Optional[str] = None
    admin_area: Optional[str] = None
    source: str = "qweather"
    now: WeatherNow
