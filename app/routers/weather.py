from fastapi import APIRouter, HTTPException, Query
import logging

from app.schemas import WeatherResponse
from app.services.weather import fetch_weather_now

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/weather/now", response_model=WeatherResponse)
async def weather_now(
    city: str | None = Query(default=None, description="城市名，例如：杭州"),
    location_id: str | None = Query(
        default=None,
        alias="locationId",
        description="和风 LocationID，可选",
    ),
    lat: float | None = Query(default=None, description="纬度，可选"),
    lon: float | None = Query(default=None, description="经度，可选"),
):
    try:
        payload = await fetch_weather_now(
            city=city,
            location_id=location_id,
            lat=lat,
            lon=lon,
        )
        response = WeatherResponse(**payload)
        logger.info(
            "Weather query success city_param=%s location_id=%s lat=%s lon=%s resolved_city=%s resolved_lat=%s resolved_lon=%s",
            city or response.city,
            location_id,
            lat,
            lon,
            response.city,
            response.lat,
            response.lon,
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "weather_fetch_failed",
                "message": str(exc),
            },
        )
