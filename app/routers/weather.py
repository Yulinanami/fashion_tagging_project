from fastapi import APIRouter, HTTPException, Query

from app.schemas import WeatherResponse
from app.services.weather import fetch_weather_now

router = APIRouter()


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
        return await fetch_weather_now(
            city=city,
            location_id=location_id,
            lat=lat,
            lon=lon,
        )
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
