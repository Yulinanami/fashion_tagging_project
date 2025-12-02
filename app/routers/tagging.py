from pathlib import Path
import shutil
import tempfile

from fastapi import APIRouter, File, UploadFile

from app.services.tagging import tag_image
from app.services.renaming import build_new_name

router = APIRouter()


@router.post("/tag-image")
async def tag_image_api(file: UploadFile = File(...)):
    """
    接收一张图片，返回时尚标签 JSON
    """
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        tags = tag_image(tmp_path)  # 直接复用打标签逻辑
        return {"filename": file.filename, "tags": tags}
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/tag-and-suggest-name")
async def tag_and_suggest_name_api(file: UploadFile = File(...)):
    """
    接收图片，返回：标签 + 推荐文件名（不真正重命名，只是给前端参考）
    """
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        tags = tag_image(tmp_path)
        suggested_name = build_new_name(tags, index=1, ext=suffix.lower())
        return {
            "original_filename": file.filename,
            "suggested_name": suggested_name,
            "tags": tags,
        }
    finally:
        tmp_path.unlink(missing_ok=True)
