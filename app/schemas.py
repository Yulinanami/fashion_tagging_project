from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


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
    lat: Optional[str] = None
    lon: Optional[str] = None
    update_time: Optional[str] = None
    admin_area: Optional[str] = None
    source: str = "qweather"
    now: WeatherNow


class OutfitTags(BaseModel):
    style: List[str] = []
    season: List[str] = []
    scene: List[str] = []
    weather: List[str] = []
    general: List[str] = []


class OutfitOut(BaseModel):
    id: int
    title: str
    image_url: Optional[str] = Field(None, alias="imageUrl")
    gender: str
    tags: OutfitTags
    images: List[str] = Field(default_factory=list, alias="images")
    is_favorite: bool = Field(False, alias="isFavorite")

    class Config:
        from_attributes = True
        allow_population_by_field_name = True


class PagedOutfits(BaseModel):
    items: List[OutfitOut]
    page: int
    page_size: int = Field(..., alias="pageSize")
    total: int

    class Config:
        allow_population_by_field_name = True


class ToggleFavoriteResponse(BaseModel):
    is_favorite: bool = Field(..., alias="isFavorite")

    class Config:
        allow_population_by_field_name = True


class TryOnResponse(BaseModel):
    job_id: str = Field(..., alias="jobId")
    result_image_base64: str = Field(..., alias="resultImageBase64")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    model: str
    prompt: str
    message: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
