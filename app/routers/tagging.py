from pathlib import Path
import shutil
import tempfile
import logging

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from app.services.tagging import tag_image
from app.services.renaming import build_new_name
from google.api_core.exceptions import ResourceExhausted

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/tag-image")
async def tag_image_api(
    file: UploadFile = File(...),
    model: str | None = Form(default=None, description="标签模型，如 gemini-2.5-flash 或 gemini-2.5-flash-lite"),
):
    """
    接收一张图片，返回时尚标签 JSON
    """
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        tags = tag_image(tmp_path, model_name=model)  # 直接复用打标签逻辑
        logger.info("Tag-image success filename=%s model=%s", file.filename, tags.get("_model_used") or model or "default")
        return {"filename": file.filename, "tags": tags}
    except ResourceExhausted:
        raise HTTPException(
            status_code=429,
            detail={"code": "tagging_quota_exceeded", "message": "打标签服务配额不足，请稍后重试或切换模型"},
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/tag-and-suggest-name")
async def tag_and_suggest_name_api(
    file: UploadFile = File(...),
    model: str | None = Form(default=None, description="标签模型，如 gemini-2.5-flash 或 gemini-2.5-flash-lite"),
):
    """
    接收图片，返回：标签 + 推荐文件名（不真正重命名，只是给前端参考）
    """
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        tags = tag_image(tmp_path, model_name=model)
        suggested_name = build_new_name(tags, index=1, ext=suffix.lower())
        logger.info("Tag-and-suggest success filename=%s model=%s suggested=%s", file.filename, tags.get("_model_used") or model or "default", suggested_name)
        return {
            "original_filename": file.filename,
            "suggested_name": suggested_name,
            "tags": tags,
        }
    except ResourceExhausted:
        raise HTTPException(
            status_code=429,
            detail={"code": "tagging_quota_exceeded", "message": "打标签服务配额不足，请稍后重试或切换模型"},
        )
    finally:
        tmp_path.unlink(missing_ok=True)
