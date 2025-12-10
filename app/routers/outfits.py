from __future__ import annotations

import json
import logging
from typing import List, Optional, Set
from pathlib import Path
import time

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
    File,
    UploadFile,
    Form,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Favorite, Outfit, User
from app.schemas import (
    OutfitOut,
    OutfitRecommendation,
    OutfitRecommendationRequest,
    PagedOutfits,
    ToggleFavoriteResponse,
)
from app.services.tagging import tag_image
from app.services.renaming import build_new_name
from app.services.llm_client import get_model
from app.services.outfit_serializers import (
    parse_tags,
    is_user_upload,
    serialize_outfit,
)
from PIL import Image
from google.api_core.exceptions import ResourceExhausted
import tempfile
import shutil
import os
from app.routers.auth import _get_current_user, _get_current_user_optional
from fastapi import status as http_status

router = APIRouter()
logger = logging.getLogger(__name__)
_recommendation_models: dict[str, tuple[object, str]] = {}


def _get_recommendation_model(model_name: Optional[str] = None) -> tuple[object, str]:
    key = (model_name or "").strip() or "default"
    if key not in _recommendation_models:
        model = get_model(model_name)
        name = (
            getattr(model, "model_name", None)
            or getattr(model, "_model", None)
            or model_name
            or "unknown"
        )
        _recommendation_models[key] = (model, name)
    return _recommendation_models[key]


def _save_user_upload_image(src: Path, dst: Path):
    """将用户上传的图片转换为 JPEG 保存，必要时做直接拷贝兜底。"""
    try:
        with Image.open(src) as img:
            img.convert("RGB").save(dst, format="JPEG", quality=90)
    except Exception:
        shutil.copyfile(src, dst)


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
        key=lambda o: (not is_user_upload(o), o.id),
    )
    for outfit in sorted_candidates:
        tags = parse_tags(outfit.tags)
        season_set = set(tags.season or [])
        if season_set & preferred_seasons:
            return outfit.id
    return sorted_candidates[0].id if sorted_candidates else 0


@router.post("/outfits/upload", response_model=OutfitOut)
async def upload_outfit(
    file: UploadFile = File(..., description="穿搭图片"),
    model: str | None = Form(default=None, description="打标签模型，可选"),
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
        # 在后台线程调用打标签，避免阻塞事件循环
        raw_tags = await run_in_threadpool(tag_image, tmp_path, model_name=model)
        tags = _map_tags(raw_tags)
        suggested_name = build_new_name(
            raw_tags, index=int(time.time()), ext=suffix.lower()
        )
        static_root = Path("static") / "outfits" / "user_uploads"
        static_root.mkdir(parents=True, exist_ok=True)
        target_path = static_root / suggested_name

        # 保存为 JPEG 保证兼容
        await run_in_threadpool(_save_user_upload_image, tmp_path, target_path)

        # 入库
        outfit = Outfit(
            title=_build_title(tags, suggested_name.rsplit(".", 1)[0]),
            image_url=f"/static/outfits/user_uploads/{target_path.name}",
            gender=tags.get("gender") or "unisex",
            is_user_upload=True,
            tags=json.dumps(tags, ensure_ascii=False),
            style=tags.get("style")[0] if tags.get("style") else None,
            season=tags.get("season")[0] if tags.get("season") else None,
            scene=tags.get("scene")[0] if tags.get("scene") else None,
            weather=tags.get("weather")[0] if tags.get("weather") else None,
        )
        db.add(outfit)
        db.commit()
        db.refresh(outfit)
        logger.info(
            "用户上传穿搭 user_id=%s outfit_id=%s file=%s",
            current_user.id,
            outfit.id,
            target_path.name,
        )
        favorite_ids = {
            row.outfit_id
            for row in db.query(Favorite.outfit_id).filter(
                Favorite.user_id == current_user.id
            )
        }
        return serialize_outfit(outfit, favorite_ids)
    except ResourceExhausted as exc:
        logger.warning(
            "Upload outfit tagging quota exhausted model=%s: %s",
            model or "default",
            exc,
        )
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "tagging_quota_exceeded",
                "message": "打标签服务配额不足，请稍后重试或切换模型",
            },
        )
    except Exception as exc:
        logger.exception("上传穿搭失败: %s", exc)
        raise HTTPException(
            status_code=500, detail={"code": "upload_failed", "message": str(exc)}
        )
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
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "穿搭不存在"},
        )
    if not is_user_upload(outfit):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "只能删除自己上传的穿搭"},
        )
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
    current_user: Optional[User] = Depends(_get_current_user_optional),
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
        query = query.filter(
            or_(Outfit.title.ilike(pattern), Outfit.tags.ilike(pattern))
        )

    total = query.count()
    items = query.order_by(Outfit.id.asc()).offset((page - 1) * size).limit(size).all()

    favorite_ids: Set[int] = set()
    if current_user:
        favorite_ids = {
            row.outfit_id
            for row in db.query(Favorite.outfit_id).filter(
                Favorite.user_id == current_user.id
            )
        }

    return PagedOutfits.model_validate(
        {
            "items": [serialize_outfit(item, favorite_ids) for item in items],
            "page": page,
            "pageSize": size,
            "total": total,
        }
    )


@router.get("/outfits/{outfit_id}", response_model=OutfitOut)
def get_outfit(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_current_user_optional),
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
            row.outfit_id
            for row in db.query(Favorite.outfit_id).filter(
                Favorite.user_id == current_user.id
            )
        }
    return serialize_outfit(outfit, favorite_ids)


@router.post("/outfits/recommend", response_model=OutfitRecommendation)
async def recommend_outfit(
    payload: OutfitRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_current_user_optional),
):
    candidates: List[Outfit] = (
        db.query(Outfit).order_by(Outfit.id.desc()).limit(40).all()
    )
    if not candidates:
        raise HTTPException(
            status_code=404, detail={"code": "no_outfit", "message": "暂无穿搭可推荐"}
        )

    favorite_ids: Set[int] = set()
    if current_user:
        favorite_ids = {
            row.outfit_id
            for row in db.query(Favorite.outfit_id).filter(
                Favorite.user_id == current_user.id
            )
        }

    candidate_payload = []
    for outfit in candidates:
        tags = parse_tags(outfit.tags)
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
                "isUserUpload": is_user_upload(outfit),
            }
        )

    chosen_id: Optional[int] = None
    reason = "基于当前天气的推荐"
    candidate_ids = {item["id"] for item in candidate_payload}

    try:
        model, model_name_used = _get_recommendation_model(payload.model)
        logger.info(
            "Recommend start model=%s city=%s temp=%s weather=%s candidates=%d",
            model_name_used,
            payload.city,
            payload.temperature,
            payload.weather_text,
            len(candidate_payload),
        )
        prompt = (
            "你是一个专业的穿搭推荐助手，根据当前天气从给定列表里选出最合适的一套，返回 JSON。"
            f"城市: {payload.city or '未知'}；气温(°C): {payload.temperature if payload.temperature is not None else '未知'}；"
            f"天气: {payload.weather_text or '未知'}。"
            "候选穿搭列表（只能从这里选 id）："
            f"{json.dumps(candidate_payload, ensure_ascii=False)}"
            '请仅返回合法 JSON，如：{"id": 3, "reason": "理由简短中文"}，不要有额外文本。'
            "偏好规则：高温(>=28°C)选夏季/清凉；低温(<=12°C)选秋冬/保暖；中温选春秋/四季；"
            "若有用户上传的匹配项可优先考虑。"
        )
        # LLM 调用为阻塞型，同样放入线程池防止阻塞 event loop
        response = await run_in_threadpool(model.generate_content, prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json", "", 1).strip()
        data = json.loads(raw)
        candidate_id = int(data.get("id"))
        if candidate_id in candidate_ids:
            chosen_id = candidate_id
            reason = str(data.get("reason") or reason)
            logger.info(
                "Recommend success model=%s chosen_id=%s",
                model_name_used,
                chosen_id,
            )
    except Exception as exc:
        logger.warning(
            "LLM recommend failed model=%s: %s", model_name_used, exc
        )

    if chosen_id is None:
        chosen_id = _fallback_recommendation(payload.temperature, candidates)
        reason = "根据温度的默认推荐"

    chosen = next((c for c in candidates if c.id == chosen_id), candidates[0])
    return OutfitRecommendation(
        outfit=serialize_outfit(chosen, favorite_ids),
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
    return [serialize_outfit(item, favorite_ids) for item in favorites]


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
