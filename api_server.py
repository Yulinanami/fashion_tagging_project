# api_server.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile
import shutil

from tagging import tag_image
from renaming import build_new_name

app = FastAPI(title="Fashion Tagging API")

# 允许 Android 调用（本地/局域网都放开）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/tag-image")
async def tag_image_api(file: UploadFile = File(...)):
    """
    接收一张图片，返回时尚标签 JSON
    """
    # 把上传文件存到临时文件
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        tags = tag_image(tmp_path)  # 直接复用你原来的打标签逻辑
        return {"filename": file.filename, "tags": tags}
    finally:
        # 用完删掉临时文件
        tmp_path.unlink(missing_ok=True)


@app.post("/tag-and-suggest-name")
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
        # 这里只拿 index=1 构造一个名字给前端看
        suggested_name = build_new_name(tags, index=1, ext=suffix.lower())
        return {
            "original_filename": file.filename,
            "suggested_name": suggested_name,
            "tags": tags,
        }
    finally:
        tmp_path.unlink(missing_ok=True)
