from __future__ import annotations

import base64
import logging
import asyncio
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from PIL import Image
from io import BytesIO

from app.config import DASHSCOPE_API_KEY, TRYON_MODEL, TRYON_RESULT_DIR

logger = logging.getLogger(__name__)
SUPPORTED_TRYON_MODELS = {"aitryon", "aitryon-plus"}


class TryOnServiceError(RuntimeError):
    """外部换装服务异常"""


def _get_api_key() -> str:
    if not DASHSCOPE_API_KEY:
        raise TryOnServiceError("未配置 DASHSCOPE_API_KEY")
    return DASHSCOPE_API_KEY


def _normalize_model(model: Optional[str]) -> str:
    name = (model or TRYON_MODEL).strip() or TRYON_MODEL
    if name not in SUPPORTED_TRYON_MODELS:
        logger.warning("Unsupported try-on model %s, fallback to %s", name, TRYON_MODEL)
        return TRYON_MODEL
    return name


def _prepare_image(data: bytes, max_side: int = 4000, min_side: int = 150) -> tuple[bytes, str]:
    """
    确保图片分辨率满足接口要求：最长边 < max_side，最短边 > min_side，大小 < 5MB。
    返回 (bytes, mime)
    """
    try:
        img = Image.open(BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise TryOnServiceError(f"读取图片失败：{exc}")

    w, h = img.size
    if min(w, h) < min_side:
        raise TryOnServiceError("图片尺寸过小，请选择长宽至少 150 像素的图片")

    scale = 1.0
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = img.size

    buffer = BytesIO()
    quality = 92
    img.save(buffer, format="JPEG", quality=quality)
    size_bytes = buffer.tell()

    # 控制文件大小在 5MB 以内
    while size_bytes > 5 * 1024 * 1024 and quality > 70:
        quality -= 5
        buffer.seek(0)
        buffer.truncate()
        img.save(buffer, format="JPEG", quality=quality)
        size_bytes = buffer.tell()

    buffer.seek(0)
    return buffer.read(), "image/jpeg"


async def _get_upload_policy(client: httpx.AsyncClient, model: str) -> Dict[str, Any]:
    url = "https://dashscope.aliyuncs.com/api/v1/uploads"
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }
    params = {"action": "getPolicy", "model": model}
    resp = await client.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise TryOnServiceError(f"获取上传凭证失败: HTTP {resp.status_code} {resp.text}")
    return resp.json().get("data") or {}


async def _upload_to_oss(policy: Dict[str, Any], file_name: str, data: bytes, mime: Optional[str]) -> str:
    key = f"{policy['upload_dir']}/{file_name}"
    files = {
        "OSSAccessKeyId": (None, policy["oss_access_key_id"]),
        "Signature": (None, policy["signature"]),
        "policy": (None, policy["policy"]),
        "x-oss-object-acl": (None, policy["x_oss_object_acl"]),
        "x-oss-forbid-overwrite": (None, policy["x_oss_forbid_overwrite"]),
        "key": (None, key),
        "success_action_status": (None, "200"),
        "file": (file_name, data, mime or "image/jpeg"),
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(policy["upload_host"], files=files)
    if resp.status_code != 200:
        raise TryOnServiceError(f"上传文件失败: HTTP {resp.status_code} {resp.text}")
    return f"oss://{key}"


async def _create_tryon_task(client: httpx.AsyncClient, person_url: str, garment_url: str, model: str) -> str:
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis"
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
        "X-DashScope-OssResourceResolve": "enable",
    }
    payload = {
        "model": model,
        "input": {
            "person_image_url": person_url,
            "top_garment_url": garment_url,
        },
        "parameters": {
            "resolution": -1,
            "restore_face": True,
        },
    }
    resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise TryOnServiceError(f"创建试衣任务失败: HTTP {resp.status_code} {resp.text}")
    output = (resp.json().get("output")) or {}
    task_id = output.get("task_id")
    status = output.get("task_status")
    if not task_id:
        raise TryOnServiceError(f"未返回 task_id: {resp.text}")
    logger.info("Try-on task created task_id=%s status=%s", task_id, status)
    return task_id


async def _poll_task(task_id: str, interval: float = 3.0, timeout: int = 300) -> Dict[str, Any]:
    url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {_get_api_key()}"}
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise TryOnServiceError(f"查询任务失败: HTTP {resp.status_code} {resp.text}")
            data = resp.json()
            output = data.get("output") or {}
            status = output.get("task_status")
            if status == "SUCCEEDED":
                return output
            if status in ("FAILED", "UNKNOWN", "CANCELED"):
                raise TryOnServiceError(f"任务失败或异常: {status}, full: {data}")
            if time.time() - start > timeout:
                raise TryOnServiceError("等待超时，请稍后重试")
            await asyncio.sleep(interval)


async def _download_image(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise TryOnServiceError(f"下载结果失败: HTTP {resp.status_code}")
        return resp.content


async def generate_tryon_image(
    user_bytes: bytes,
    outfit_bytes: bytes,
    user_mime: Optional[str] = None,
    outfit_mime: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用阿里云 DashScope OutfitAnyone，完成上传、提交、轮询并返回 base64 + 静态链接。
    """
    model_name = _normalize_model(model)
    logger.info("Try-on request using model=%s", model_name)
    async with httpx.AsyncClient(timeout=60.0) as client:
        policy = await _get_upload_policy(client, model_name)
    processed_person, person_mime = _prepare_image(user_bytes)
    processed_garment, garment_mime = _prepare_image(outfit_bytes)

    person_url = await _upload_to_oss(policy, "person.jpg", processed_person, person_mime)
    garment_url = await _upload_to_oss(policy, "garment.jpg", processed_garment, garment_mime)

    async with httpx.AsyncClient(timeout=60.0) as client:
        task_id = await _create_tryon_task(client, person_url, garment_url, model_name)
    output = await _poll_task(task_id)
    image_url = output.get("image_url")
    if not image_url:
        raise TryOnServiceError("任务成功但未返回 image_url")

    img_bytes = await _download_image(image_url)

    result_dir = Path(TRYON_RESULT_DIR)
    result_dir.mkdir(parents=True, exist_ok=True)
    file_path = result_dir / f"{task_id}.png"
    with file_path.open("wb") as f:
        f.write(img_bytes)
    try:
        static_url = f"/static/{file_path.relative_to(Path('static')).as_posix()}"
    except ValueError:
        static_url = None

    image_b64 = base64.b64encode(img_bytes).decode("utf-8")

    return {
        "result_image_base64": image_b64,
        "model": model_name,
        "prompt": f"dashscope outfitanyone {model_name}",
        "job_id": task_id,
        "image_url": static_url or image_url,
    }
