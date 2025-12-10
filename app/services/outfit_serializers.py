from __future__ import annotations

"""
Helpers to keep outfit router lean: parsing tags, collecting images, and building response models.
"""

import json
from pathlib import Path
from typing import List, Optional, Set

from app.models import Favorite, Outfit
from app.schemas import OutfitOut, OutfitTags


def static_url_for(path: Path) -> str:
    """Convert a static file path to a web-accessible URL."""
    rel = path.relative_to(Path("static"))
    return f"/static/{rel.as_posix()}"


def parse_tags(raw: Optional[str]) -> OutfitTags:
    if not raw:
        return OutfitTags()
    try:
        data = json.loads(raw)
        return OutfitTags(**{**OutfitTags().model_dump(), **data})
    except Exception:
        items = [item.strip() for item in raw.split(",") if item.strip()]
        return OutfitTags(general=items)


def collect_images(outfit_id: int, cover: Optional[str]) -> List[str]:
    """
    Collect all images for the outfit from static/outfits, keeping cover first when present.
    Pattern: outfit_<id>_<number>.*.
    """
    images: List[str] = []
    if cover:
        images.append(cover)
    pattern_root = Path("static") / "outfits"
    if pattern_root.exists():
        for path in sorted(pattern_root.glob(f"outfit_{outfit_id}_*")):
            suffix_part = path.stem.split("_")[-1]
            if not suffix_part.isdigit():
                continue
            url = static_url_for(path)
            if url not in images:
                images.append(url)
    return images


def is_user_upload(outfit: Outfit) -> bool:
    return bool(outfit.image_url and "/user_uploads/" in outfit.image_url)


def serialize_outfit(outfit: Outfit, favorite_ids: Set[int]) -> OutfitOut:
    return OutfitOut(
        id=outfit.id,
        title=outfit.title,
        image_url=outfit.image_url,
        gender=outfit.gender,
        tags=parse_tags(outfit.tags),
        images=collect_images(outfit.id, outfit.image_url),
        is_user_upload=is_user_upload(outfit),
        is_favorite=outfit.id in favorite_ids,
    )
