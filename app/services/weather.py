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
    # 允许 city 传入 "lat,lon" 或 "lon,lat" 以防前端直接拼接
    if city and "," in city and lat is None and lon is None:
        parts = [p.strip() for p in city.split(",", maxsplit=1)]
        try:
            first, second = float(parts[0]), float(parts[1])
            # 和风要求 "lon,lat"
            if abs(first) <= 90 and abs(second) <= 180:
                # 大概率是 lat, lon
                lat, lon = first, second
            else:
                # 大概率是 lon, lat
                lon, lat = first, second
        except Exception:
            # 如果解析失败，继续走城市名逻辑
            lat = None
            lon = None

    if location_id:
        return location_id, {"name": city}
    if lat is not None and lon is not None:
        # 通过经纬度反查城市，拿到 LocationID 和名称
        lookup = await _get_json(
            "/geo/v2/city/lookup",
            {"location": f"{lon},{lat}", "lang": QWEATHER_LANG},
        )
        locations = lookup.get("location") or []
        best_match = locations[0] if locations else {}
        resolved_id = (
            best_match.get("id")
            or best_match.get("locationId")
            or f"{lon},{lat}"
        )
        return resolved_id, {
            "name": best_match.get("name") or city or f"{lat},{lon}",
            "adm1": best_match.get("adm1"),
        }
    if city:
        lookup = await _get_json(
            "/geo/v2/city/lookup",
            {"location": city, "lang": QWEATHER_LANG},
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
    resolved_city = location.get("name") or city or resolved_id
    resolved_lat = location.get("lat") or (str(lat) if lat is not None else None)
    resolved_lon = location.get("lon") or (str(lon) if lon is not None else None)
    resolved_location_id = (
        location.get("id")
        or location.get("locationId")
        or resolved_id
    )
    result = {
        "city": resolved_city,
        "admin_area": location.get("adm1") or location.get("adm2") or location.get("country"),
        "location_id": resolved_location_id,
        "lat": resolved_lat,
        "lon": resolved_lon,
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
