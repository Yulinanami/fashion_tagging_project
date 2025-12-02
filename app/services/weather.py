import time
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import HTTPException

from app.config import (
    QWEATHER_HOST,
    QWEATHER_KEY,
    QWEATHER_LANG,
    QWEATHER_TIMEOUT,
    QWEATHER_UNIT,
    QWEATHER_CACHE_SECONDS,
)


BASE_URL = f"https://{QWEATHER_HOST.strip('/')}"
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


async def _get_json(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not QWEATHER_KEY:
        raise HTTPException(
            status_code=500,
            detail={"code": "weather_config_missing", "message": "未配置 QWeather Key"},
        )
    url = f"{BASE_URL}{path}"
    merged_params = {**params, "key": QWEATHER_KEY}
    try:
        async with httpx.AsyncClient(
            timeout=QWEATHER_TIMEOUT,
            headers={"Accept": "application/json"},
        ) as client:
            response = await client.get(url, params=merged_params)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "weather_request_failed", "message": str(exc)},
        )
    try:
        data = response.json()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={"code": "weather_parse_error", "message": "天气服务返回内容无法解析"},
        )
    if data.get("code") != "200":
        detail_msg = data.get("message") or data.get("fxLink") or str(data.get("code"))
        raise HTTPException(
            status_code=502,
            detail={
                "code": "weather_api_error",
                "message": f"天气服务错误：{data.get('code')} {detail_msg}",
            },
        )
    return data


async def _resolve_location(
    city: Optional[str],
    location_id: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
) -> Tuple[str, Dict[str, Any]]:
    if location_id:
        return location_id, {"name": city}
    if lat is not None and lon is not None:
        return f"{lon},{lat}", {"name": city or f"{lat},{lon}"}
    if city:
        lookup = await _get_json(
            "/geo/v2/city/lookup",
            {"location": city},
        )
        locations = lookup.get("location") or []
        if not locations:
            raise HTTPException(
                status_code=404,
                detail={"code": "city_not_found", "message": f"未找到城市：{city}"},
            )
        best_match = locations[0]
        location_id = best_match.get("id") or best_match.get("locationId")
        if not location_id:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "location_id_missing",
                    "message": "天气服务未返回城市 ID",
                },
            )
        return location_id, best_match
    raise HTTPException(
        status_code=400,
        detail={
            "code": "missing_location",
            "message": "请提供 city、location_id 或经纬度",
        },
    )


async def fetch_weather_now(
    city: Optional[str] = None,
    location_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Dict[str, Any]:
    resolved_id, location = await _resolve_location(city, location_id, lat, lon)
    # 简单缓存，降低频率限制
    cache_key = resolved_id
    now_ts = time.time()
    cached = _cache.get(cache_key)
    if cached and now_ts - cached[0] < QWEATHER_CACHE_SECONDS:
        return cached[1]
    weather = await _get_json(
        "/v7/weather/now",
        {
            "location": resolved_id,
            "lang": QWEATHER_LANG,
            "unit": QWEATHER_UNIT,
        },
    )
    now = weather.get("now") or {}
    return {
        "city": location.get("name") or city or resolved_id,
        "admin_area": location.get("adm1"),
        "location_id": resolved_id,
        "update_time": weather.get("updateTime"),
        "source": "qweather",
        "now": {
            "temp": now.get("temp"),
            "text": now.get("text"),
            "feels_like": now.get("feelsLike"),
            "wind_dir": now.get("windDir"),
            "wind_scale": now.get("windScale"),
            "humidity": now.get("humidity"),
            "icon": now.get("icon"),
        },
    }
    _cache[cache_key] = (time.time(), result)
    return result
