from __future__ import annotations

import json
import logging
from typing import List, Optional, Set
from pathlib import Path
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status, File, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Favorite, Outfit, User
from app.schemas import (
    OutfitOut,
    OutfitRecommendation,
    OutfitRecommendationRequest,
    OutfitTags,
    PagedOutfits,
    ToggleFavoriteResponse,
)
from app.services.tagging import tag_image
from app.services.renaming import build_new_name
from app.services.llm_client import get_model
from PIL import Image
import tempfile
import shutil
import os
from app.routers.auth import _get_current_user
from fastapi import status as http_status

router = APIRouter()
logger = logging.getLogger(__name__)
_recommendation_model = None


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


def _collect_images(outfit_id: int, cover: Optional[str]) -> List[str]:
    """收集静态目录中的多张穿搭图片，约定文件名为 outfit_<id>_<数字>.*"""
    images: List[str] = []
    if cover:
        images.append(cover)
    pattern_root = Path("static") / "outfits"
    if pattern_root.exists():
        for path in sorted(pattern_root.glob(f"outfit_{outfit_id}_*")):
            # 仅保留后缀为数字的文件，避免同图别名重复
            stem = path.stem
            suffix_part = stem.split("_")[-1]
            if not suffix_part.isdigit():
                continue
            url = f"/static/outfits/{path.name}"
            if url not in images:
                images.append(url)
    return images


def _is_user_upload(outfit: Outfit) -> bool:
    return bool(outfit.image_url and "/user_uploads/" in outfit.image_url)


def _serialize(outfit: Outfit, favorite_ids: Set[int]) -> OutfitOut:
    return OutfitOut(
        id=outfit.id,
        title=outfit.title,
        image_url=outfit.image_url,
        gender=outfit.gender,
        tags=_parse_tags(outfit.tags),
        images=_collect_images(outfit.id, outfit.image_url),
        is_user_upload=_is_user_upload(outfit),
        is_favorite=outfit.id in favorite_ids,
    )


def _get_recommendation_model():
    global _recommendation_model
    if _recommendation_model is None:
        _recommendation_model = get_model()
    return _recommendation_model


def _temperature_bucket(temp: Optional[float]) -> str:
    if temp is None:
        return "mild"
    if temp >= 28:
        return "hot"
    if temp <= 12:
        return "cold"
    return "mild"


def _fallback_recommendation(
    temp: Optional[float],
    candidates: List[Outfit],
) -> int:
    """
    简单按温度和季节匹配的兜底逻辑，优先用户上传。
    """
    bucket = _temperature_bucket(temp)
    preferred_seasons = {
        "hot": {"夏季", "春季", "四季"},
        "cold": {"冬季", "秋季", "四季"},
        "mild": {"春季", "秋季", "四季"},
    }[bucket]

    sorted_candidates = sorted(
        candidates,
        key=lambda o: (not _is_user_upload(o), o.id),
    )
    for outfit in sorted_candidates:
        tags = _parse_tags(outfit.tags)
        season_set = set(tags.season or [])
        if season_set & preferred_seasons:
            return outfit.id
    return sorted_candidates[0].id if sorted_candidates else 0


@router.post("/outfits/upload", response_model=OutfitOut)
async def upload_outfit(
    file: UploadFile = File(..., description="穿搭图片"),
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user),
):
    # 保存上传文件到静态目录
    suffix = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        # 生成建议文件名
        raw_tags = tag_image(tmp_path)
        tags = _map_tags(raw_tags)
        suggested_name = build_new_name(raw_tags, index=int(time.time()), ext=suffix.lower())
        static_root = Path("static") / "outfits" / "user_uploads"
        static_root.mkdir(parents=True, exist_ok=True)
        target_path = static_root / suggested_name

        # 保存为 JPEG 保证兼容
        try:
            img = Image.open(tmp_path).convert("RGB")
            img.save(target_path, format="JPEG", quality=90)
        except Exception:
            shutil.copyfile(tmp_path, target_path)

        # 入库
        outfit = Outfit(
            title=_build_title(tags, suggested_name.rsplit(".", 1)[0]),
            image_url=f"/static/outfits/user_uploads/{target_path.name}",
            gender=tags.get("gender") or "unisex",
            tags=json.dumps(tags, ensure_ascii=False),
            style=tags.get("style")[0] if tags.get("style") else None,
            season=tags.get("season")[0] if tags.get("season") else None,
            scene=tags.get("scene")[0] if tags.get("scene") else None,
            weather=tags.get("weather")[0] if tags.get("weather") else None,
        )
        db.add(outfit)
        db.commit()
        db.refresh(outfit)
        logger.info("用户上传穿搭 user_id=%s outfit_id=%s file=%s", current_user.id, outfit.id, target_path.name)
        favorite_ids = {
            row.outfit_id for row in db.query(Favorite.outfit_id).filter(Favorite.user_id == current_user.id)
        }
        return _serialize(outfit, favorite_ids)
    except Exception as exc:
        logger.exception("上传穿搭失败: %s", exc)
        raise HTTPException(status_code=500, detail={"code": "upload_failed", "message": str(exc)})
    finally:
        tmp_path.unlink(missing_ok=True)


def _map_tags(raw: dict) -> dict:
    """将打标签结果映射为 UI 需要的字段"""
    style = []
    season = []
    scene = []
    weather = []
    general = []
    if isinstance(raw, dict):
        if raw.get("overall_style"):
            style.append(str(raw.get("overall_style")))
        if raw.get("season"):
            season.append(str(raw.get("season")))
        occasions = raw.get("suitable_occasion")
        if isinstance(occasions, list):
            scene.extend([str(o) for o in occasions if o])
        if raw.get("weather"):
            weather.append(str(raw.get("weather")))
        keywords = raw.get("fashion_keywords")
        if isinstance(keywords, list):
            general.extend([str(k) for k in keywords if k])
        palette = raw.get("color_palette")
        if isinstance(palette, list):
            general.extend([str(c) for c in palette if c])
    return {
        "gender": raw.get("gender") if isinstance(raw, dict) else None,
        "style": style,
        "season": season,
        "scene": scene,
        "weather": weather,
        "general": general,
    }


def _build_title(mapped_tags: dict, fallback: str) -> str:
    parts: List[str] = []
    gender = mapped_tags.get("gender")
    if gender:
        parts.append(str(gender))
    for key in ("style", "scene", "season", "weather"):
        values = mapped_tags.get(key) or []
        if isinstance(values, list) and values:
            parts.append(str(values[0]))
    general = mapped_tags.get("general") or []
    if isinstance(general, list) and general:
        parts.append(str(general[0]))
    title = "·".join([p for p in parts if p])
    return title or fallback


@router.delete("/outfits/{outfit_id}")
def delete_outfit(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user),
):
    outfit = db.query(Outfit).filter(Outfit.id == outfit_id).first()
    if not outfit:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "穿搭不存在"})
    if not _is_user_upload(outfit):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail={"code": "forbidden", "message": "只能删除自己上传的穿搭"})
    # 删除文件
    if outfit.image_url and outfit.image_url.startswith("/static/"):
        file_path = Path("static") / Path(outfit.image_url).relative_to("/static")
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass
    db.delete(outfit)
    db.commit()
    return {"success": True}


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


@router.post("/outfits/recommend", response_model=OutfitRecommendation)
async def recommend_outfit(
    payload: OutfitRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_current_user_optional),
):
    candidates: List[Outfit] = (
        db.query(Outfit)
        .order_by(Outfit.id.desc())
        .limit(40)
        .all()
    )
    if not candidates:
        raise HTTPException(status_code=404, detail={"code": "no_outfit", "message": "暂无穿搭可推荐"})

    favorite_ids: Set[int] = set()
    if current_user:
        favorite_ids = {
            row.outfit_id for row in db.query(Favorite.outfit_id).filter(Favorite.user_id == current_user.id)
        }

    candidate_payload = []
    for outfit in candidates:
        tags = _parse_tags(outfit.tags)
        candidate_payload.append(
            {
                "id": outfit.id,
                "title": outfit.title,
                "gender": outfit.gender,
                "style": tags.style,
                "season": tags.season,
                "scene": tags.scene,
                "weather": tags.weather,
                "general": tags.general,
                "isUserUpload": _is_user_upload(outfit),
            }
        )

    chosen_id: Optional[int] = None
    reason = "基于当前天气的推荐"
    candidate_ids = {item["id"] for item in candidate_payload}

    try:
        model = _get_recommendation_model()
        prompt = (
            "你是一个专业的穿搭推荐助手，根据当前天气从给定列表里选出最合适的一套，返回 JSON。"
            f"城市: {payload.city or '未知'}；气温(°C): {payload.temperature if payload.temperature is not None else '未知'}；"
            f"天气: {payload.weather_text or '未知'}。"
            "候选穿搭列表（只能从这里选 id）："
            f"{json.dumps(candidate_payload, ensure_ascii=False)}"
            "请仅返回合法 JSON，如：{\"id\": 3, \"reason\": \"理由简短中文\"}，不要有额外文本。"
            "偏好规则：高温(>=28°C)选夏季/清凉；低温(<=12°C)选秋冬/保暖；中温选春秋/四季；"
            "若有用户上传的匹配项可优先考虑。"
        )
        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json", "", 1).strip()
        data = json.loads(raw)
        candidate_id = int(data.get("id"))
        if candidate_id in candidate_ids:
            chosen_id = candidate_id
            reason = str(data.get("reason") or reason)
    except Exception as exc:
        logger.warning("LLM recommend failed: %s", exc)

    if chosen_id is None:
        chosen_id = _fallback_recommendation(payload.temperature, candidates)
        reason = "根据温度的默认推荐"

    chosen = next((c for c in candidates if c.id == chosen_id), candidates[0])
    return OutfitRecommendation(
        outfit=_serialize(chosen, favorite_ids),
        reason=reason,
    )


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
    return ToggleFavoriteResponse.model_validate({"isFavorite": True})


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
    return ToggleFavoriteResponse.model_validate({"isFavorite": False})
