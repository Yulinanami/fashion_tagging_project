import logging
import uuid
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import TryOnResponse
from app.services.tryon import TryOnServiceError, generate_tryon_image

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/tryon", response_model=TryOnResponse)
async def try_on(
    user_image: UploadFile = File(..., description="用户人像"),
    outfit_image: UploadFile = File(..., description="穿搭/衣物图片"),
    model: str | None = Form(
        default=None, description="换装模型，如 aitryon / aitryon-plus"
    ),
):
    user_bytes = await user_image.read()
    outfit_bytes = await outfit_image.read()
    if not user_bytes:
        raise HTTPException(
            status_code=400,
            detail={"code": "user_image_missing", "message": "人像为空"},
        )
    if not outfit_bytes:
        raise HTTPException(
            status_code=400,
            detail={"code": "outfit_image_missing", "message": "穿搭图为空"},
        )

    try:
        result = await generate_tryon_image(
            user_bytes=user_bytes,
            outfit_bytes=outfit_bytes,
            user_mime=user_image.content_type,
            outfit_mime=outfit_image.content_type,
            model=model,
        )
        job_id = result.get("job_id") or uuid.uuid4().hex
        logger.info(
            "Try-on succeed job_id=%s user_image=%s outfit_image=%s model=%s",
            job_id,
            user_image.filename,
            outfit_image.filename,
            result.get("model"),
        )
        return {
            "jobId": job_id,
            "resultImageBase64": result["result_image_base64"],
            "imageUrl": result.get("image_url"),
            "model": result["model"],
            "prompt": result["prompt"],
            "message": "换装完成",
        }
    except TryOnServiceError as exc:
        logger.warning("Try-on service error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"code": "try_on_failed", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Try-on failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"code": "try_on_failed", "message": str(exc)},
        )
