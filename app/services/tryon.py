from __future__ import annotations

import base64
import logging
import asyncio
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import TRYON_API_KEY, TRYON_API_URL, TRYON_RESULT_DIR

logger = logging.getLogger(__name__)


class TryOnServiceError(RuntimeError):
    """外部换装服务异常"""


async def _submit_job(
    person_bytes: bytes,
    garment_bytes: bytes,
    person_mime: Optional[str],
    garment_mime: Optional[str],
) -> Tuple[str, str]:
    url = f"{TRYON_API_URL.rstrip('/')}/api/v1/tryon"
    headers = {"Authorization": f"Bearer {TRYON_API_KEY}"}
    files = {
        "person_images": ("person.jpg", person_bytes, person_mime or "image/jpeg"),
        "garment_images": ("garment.jpg", garment_bytes, garment_mime or "image/jpeg"),
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, files=files, data={"fast_mode": "false"})
        if resp.status_code >= 400:
            raise TryOnServiceError(f"提交失败：HTTP {resp.status_code} {resp.text}")
        data = resp.json()
        job_id = data.get("jobId")
        status_url = data.get("statusUrl")
        if not job_id or not status_url:
            raise TryOnServiceError("提交成功但未返回 jobId/statusUrl")
        return job_id, status_url


async def _poll_status(status_url: str, max_wait: int = 180, interval: float = 2.0) -> Dict[str, Any]:
    url = status_url if status_url.startswith("http") else f"{TRYON_API_URL.rstrip('/')}{status_url}"
    headers = {"Authorization": f"Bearer {TRYON_API_KEY}"}
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                raise TryOnServiceError(f"查询失败：HTTP {resp.status_code} {resp.text}")
            data = resp.json()
            status = data.get("status")
            if status == "completed":
                return data
            if status == "failed":
                raise TryOnServiceError(f"任务失败：{data.get('error') or data}")
            if time.time() - start > max_wait:
                raise TryOnServiceError("等待超时，请稍后重试")
            await asyncio.sleep(interval)


async def _download_image(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise TryOnServiceError(f"下载结果失败：HTTP {resp.status_code}")
        return resp.content


async def generate_tryon_image(
    user_bytes: bytes,
    outfit_bytes: bytes,
    user_mime: Optional[str] = None,
    outfit_mime: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用第三方 try-on API，同步轮询返回结果，返回包含 base64 的 dict。
    """
    job_id, status_url = await _submit_job(user_bytes, outfit_bytes, user_mime, outfit_mime)
    logger.info("Try-on job submitted job_id=%s status_url=%s", job_id, status_url)
    status = await _poll_status(status_url)
    image_url = status.get("imageUrl")
    image_b64 = status.get("imageBase64")

    img_bytes: Optional[bytes] = None
    if image_url:
        img_bytes = await _download_image(image_url)
    elif image_b64:
        img_bytes = base64.b64decode(image_b64)
    if not img_bytes:
        raise TryOnServiceError("任务完成但未返回图片")

    # 保存到本地文件，供前端直接访问
    result_dir = Path(TRYON_RESULT_DIR)
    result_dir.mkdir(parents=True, exist_ok=True)
    file_path = result_dir / f"{job_id}.png"
    with file_path.open("wb") as f:
        f.write(img_bytes)
    try:
        static_url = f"/static/{file_path.relative_to(Path('static')).as_posix()}"
    except ValueError:
        # 如果 TRYON_RESULT_DIR 不在 static 下，仍返回 None（前端已能用 base64）
        static_url = None

    image_b64 = base64.b64encode(img_bytes).decode("utf-8")

    return {
        "result_image_base64": image_b64,
        "model": "tryon-api.com",
        "prompt": "tryon-api.com external service",
        "job_id": job_id,
        "image_url": static_url,
    }
