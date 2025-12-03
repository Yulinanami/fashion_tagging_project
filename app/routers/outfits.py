from __future__ import annotations

import json
import logging
from typing import List, Optional, Set

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Favorite, Outfit, User
from app.schemas import OutfitOut, OutfitTags, PagedOutfits, ToggleFavoriteResponse
from app.routers.auth import _get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_tags(raw: Optional[str]) -> OutfitTags:
    if not raw:
        return OutfitTags()
    try:
        data = json.loads(raw)
        return OutfitTags(**{**OutfitTags().model_dump(), **data})
    except Exception:
        # 兼容非 JSON 的字符串 tags（按逗号切分作为 general）
        items = [item.strip() for item in raw.split(",") if item.strip()]
        return OutfitTags(general=items)


def _serialize(outfit: Outfit, favorite_ids: Set[int]) -> OutfitOut:
    return OutfitOut(
        id=outfit.id,
        title=outfit.title,
        image_url=outfit.image_url,
        gender=outfit.gender,
        tags=_parse_tags(outfit.tags),
        is_favorite=outfit.id in favorite_ids,
    )


def _current_user_optional(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not authorization:
        return None
    try:
        return _get_current_user(authorization=authorization, db=db)
    except HTTPException:
        return None


@router.get("/outfits", response_model=PagedOutfits)
def list_outfits(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    gender: Optional[str] = None,
    style: Optional[str] = None,
    season: Optional[str] = None,
    scene: Optional[str] = None,
    weather: Optional[str] = None,
    tags: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_current_user_optional),
):
    query = db.query(Outfit)
    if gender:
        query = query.filter(Outfit.gender.ilike(f"%{gender}%"))
    if style:
        query = query.filter(Outfit.style.ilike(f"%{style}%"))
    if season:
        query = query.filter(Outfit.season.ilike(f"%{season}%"))
    if scene:
        query = query.filter(Outfit.scene.ilike(f"%{scene}%"))
    if weather:
        query = query.filter(Outfit.weather.ilike(f"%{weather}%"))
    if tags:
        for tag in [t.strip() for t in tags.split(",") if t.strip()]:
            query = query.filter(Outfit.tags.ilike(f"%{tag}%"))
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(Outfit.title.ilike(pattern), Outfit.tags.ilike(pattern)))

    total = query.count()
    items = (
        query.order_by(Outfit.id.asc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    favorite_ids: Set[int] = set()
    if current_user:
        favorite_ids = {
            row.outfit_id for row in db.query(Favorite.outfit_id).filter(Favorite.user_id == current_user.id)
        }

    return PagedOutfits.model_validate(
        {
            "items": [_serialize(item, favorite_ids) for item in items],
            "page": page,
            "pageSize": size,
            "total": total,
        }
    )


@router.get("/outfits/{outfit_id}", response_model=OutfitOut)
def get_outfit(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_current_user_optional),
):
    outfit = db.query(Outfit).filter(Outfit.id == outfit_id).first()
    if not outfit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "穿搭不存在"},
        )
    favorite_ids: Set[int] = set()
    if current_user:
        favorite_ids = {
            row.outfit_id for row in db.query(Favorite.outfit_id).filter(Favorite.user_id == current_user.id)
        }
    return _serialize(outfit, favorite_ids)


@router.get("/favorites", response_model=List[OutfitOut])
def list_favorites(
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    favorites = (
        db.query(Outfit)
        .join(Favorite, Favorite.outfit_id == Outfit.id)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    favorite_ids = {row.id for row in favorites}
    return [_serialize(item, favorite_ids) for item in favorites]


@router.post("/favorites/{outfit_id}", response_model=ToggleFavoriteResponse)
def add_favorite(
    outfit_id: int,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    outfit = db.query(Outfit).filter(Outfit.id == outfit_id).first()
    if not outfit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "穿搭不存在"},
        )
    existing = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.outfit_id == outfit_id)
        .first()
    )
    if not existing:
        db.add(Favorite(user_id=current_user.id, outfit_id=outfit_id))
        db.commit()
        logger.info("收藏成功 user_id=%s outfit_id=%s", current_user.id, outfit_id)
    return ToggleFavoriteResponse(is_favorite=True)


@router.delete("/favorites/{outfit_id}", response_model=ToggleFavoriteResponse)
def remove_favorite(
    outfit_id: int,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    deleted = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.outfit_id == outfit_id)
        .delete()
    )
    if deleted:
        db.commit()
        logger.info("取消收藏 user_id=%s outfit_id=%s", current_user.id, outfit_id)
    return ToggleFavoriteResponse(is_favorite=False)
