from __future__ import annotations

import json
from typing import List, Set

from sqlalchemy.orm import Session


SEED_OUTFITS: List[dict] = [
    {
        "id": 1,
        "title": "夏日通勤",
        "gender": "female",
        "style": "通勤",
        "season": "夏季",
        "scene": "通勤",
        "weather": "晴",
        "tags": {
            "style": ["简约", "通勤"],
            "season": ["夏季"],
            "scene": ["通勤"],
            "weather": ["晴"],
            "general": ["轻盈", "清爽"],
        },
    },
    {
        "id": 2,
        "title": "周末休闲",
        "gender": "unisex",
        "style": "休闲",
        "season": "四季",
        "scene": "出街",
        "weather": "多云",
        "tags": {
            "style": ["休闲"],
            "season": ["四季"],
            "scene": ["出街"],
            "weather": ["多云"],
            "general": ["牛仔", "日常"],
        },
    },
    {
        "id": 3,
        "title": "运动风",
        "gender": "male",
        "style": "运动",
        "season": "夏季",
        "scene": "运动",
        "weather": "晴",
        "tags": {
            "style": ["运动", "街头"],
            "season": ["夏季"],
            "scene": ["运动"],
            "weather": ["晴"],
            "general": ["活力"],
        },
    },
    {
        "id": 4,
        "title": "雨天通勤",
        "gender": "female",
        "style": "通勤",
        "season": "春季",
        "scene": "办公室",
        "weather": "雨天",
        "tags": {
            "style": ["通勤"],
            "season": ["春季"],
            "scene": ["办公室"],
            "weather": ["雨天"],
            "general": ["防水"],
        },
    },
    {
        "id": 5,
        "title": "晚间约会",
        "gender": "female",
        "style": "优雅",
        "season": "夏季",
        "scene": "约会",
        "weather": "晴",
        "tags": {
            "style": ["优雅"],
            "season": ["夏季"],
            "scene": ["约会"],
            "weather": ["晴"],
            "general": ["晚宴"],
        },
    },
]


def ensure_outfits_seeded(db: Session):
    from app import models

    existing_ids: Set[int] = {row.id for row in db.query(models.Outfit.id).all()}
    inserted = 0
    for item in SEED_OUTFITS:
        if item["id"] in existing_ids:
            continue
        outfit = models.Outfit(
            id=item["id"],
            title=item["title"],
            gender=item["gender"],
            style=item.get("style"),
            season=item.get("season"),
            scene=item.get("scene"),
            weather=item.get("weather"),
            tags=json.dumps(item.get("tags", {}), ensure_ascii=False),
        )
        db.add(outfit)
        inserted += 1
    if inserted:
        db.commit()
