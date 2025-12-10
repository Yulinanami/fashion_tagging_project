import json
import logging
from pathlib import Path

from PIL import Image
from google.api_core.exceptions import ResourceExhausted

from app.config import FASHION_PROMPT, MODEL_NAME
from app.services.llm_client import get_model

_model_cache = {}
SUPPORTED_TAGGING_MODELS = {"gemini-2.5-flash", "gemini-2.5-flash-lite"}
logger = logging.getLogger(__name__)


def _normalize_model(model_name: str | None) -> str:
    name = (model_name or MODEL_NAME).strip() or MODEL_NAME
    if name not in SUPPORTED_TAGGING_MODELS:
        logger.warning("Unsupported tagging model %s, fallback to %s", name, MODEL_NAME)
        return MODEL_NAME
    return name


def get_or_create_model(model_name: str | None = None):
    normalized = _normalize_model(model_name)
    key = normalized
    if key not in _model_cache:
        _model_cache[key] = get_model(normalized)
    return _model_cache[key]


def _load_image(image_path: Path):
    with Image.open(image_path) as img:
        return img.copy()


def tag_image(image_path: Path, model_name: str | None = None) -> dict:
    """
    调用大模型，对单张图片打标签，返回 Python dict。
    """
    normalized_model = _normalize_model(model_name)
    model = get_or_create_model(normalized_model)
    img = _load_image(image_path)

    def _generate(active_model, active_name):
        return active_model.generate_content([FASHION_PROMPT, img]), active_name

    try:
        response, used_model = _generate(model, normalized_model)
    except ResourceExhausted as exc:
        # 自动降级到 lite，避免配额导致整体失败
        fallback = "gemini-2.5-flash-lite"
        if normalized_model != fallback and fallback in SUPPORTED_TAGGING_MODELS:
            logger.warning(
                "Primary model %s quota exhausted, fallback to %s",
                normalized_model,
                fallback,
            )
            response, used_model = _generate(get_or_create_model(fallback), fallback)
        else:
            raise exc
    raw = response.text.strip()

    # 去掉 ```json 包裹
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip()

    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"[ERROR] 解析 JSON 失败：{image_path}")
        print(raw)
        raise e

    data["_model_used"] = used_model
    return data
