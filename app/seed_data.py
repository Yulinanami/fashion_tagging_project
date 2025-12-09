from __future__ import annotations

import json
from typing import List, Set

from sqlalchemy.orm import Session


SEED_OUTFITS: List[dict] = [
    {
        "id": 1,
        "title": "夏日通勤",
        "image_url": "/static/outfits/outfit_1_1.png",
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
        "image_url": "/static/outfits/outfit_2_1.jpg",
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
        "image_url": "/static/outfits/outfit_3_1.jpg",
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
        "image_url": "/static/outfits/outfit_4_1.jpg",
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
        "image_url": "/static/outfits/outfit_5_1.jpg",
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
    {
        "id": 6,
        "title": "秋日街头",
        "image_url": "/static/outfits/outfit_6_1.jpg",
        "gender": "unisex",
        "style": "街头",
        "season": "秋季",
        "scene": "出街",
        "weather": "阴",
        "tags": {
            "style": ["街头", "潮流"],
            "season": ["秋季"],
            "scene": ["出街"],
            "weather": ["阴"],
            "general": ["叠穿", "牛仔"],
        },
    },
    {
        "id": 7,
        "title": "冬季复古旅行",
        "image_url": "/static/outfits/outfit_7_1.jpg",
        "gender": "unisex",
        "style": "复古",
        "season": "冬季",
        "scene": "旅行",
        "weather": "雪天",
        "tags": {
            "style": ["复古"],
            "season": ["冬季"],
            "scene": ["旅行"],
            "weather": ["雪天"],
            "general": ["呢子大衣", "保暖"],
        },
    },
    {
        "id": 8,
        "title": "办公简约",
        "image_url": "/static/outfits/outfit_8_1.jpg",
        "gender": "female",
        "style": "通勤",
        "season": "四季",
        "scene": "办公室",
        "weather": "多云",
        "tags": {
            "style": ["通勤", "简约"],
            "season": ["四季"],
            "scene": ["办公室"],
            "weather": ["多云"],
            "general": ["西装", "衬衫"],
        },
    },
]


def ensure_outfits_seeded(db: Session):
    from app import models

    seed_map = {item["id"]: item for item in SEED_OUTFITS}
    existing: List[models.Outfit] = db.query(models.Outfit).all()
    existing_ids: Set[int] = {row.id for row in existing}
    updated = 0
    for row in existing:
        seed = seed_map.get(row.id)
        if not seed:
            continue
        desired_image = seed.get("image_url")
        # 统一封面为 *_1 文件，若不同则更新
        if desired_image and row.image_url != desired_image:
            row.image_url = desired_image
            db.add(row)
            updated += 1
    inserted = 0
    for item in SEED_OUTFITS:
        if item["id"] in existing_ids:
            continue
        outfit = models.Outfit(
            id=item["id"],
            title=item["title"],
            image_url=item.get("image_url"),
            gender=item["gender"],
            style=item.get("style"),
            season=item.get("season"),
            scene=item.get("scene"),
            weather=item.get("weather"),
            tags=json.dumps(item.get("tags", {}), ensure_ascii=False),
        )
        db.add(outfit)
        inserted += 1
    if inserted or updated:
        db.commit()
