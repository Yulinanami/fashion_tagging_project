import json
from pathlib import Path

from PIL import Image

from app.config import FASHION_PROMPT
from app.services.llm_client import get_model

_model = None


def get_or_create_model():
    global _model
    if _model is None:
        _model = get_model()
    return _model


def tag_image(image_path: Path) -> dict:
    """
    调用大模型，对单张图片打标签，返回 Python dict。
    """
    model = get_or_create_model()
    img = Image.open(image_path)

    response = model.generate_content([FASHION_PROMPT, img])
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

    return data
