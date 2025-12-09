import google.generativeai as genai

from app.config import API_KEY, MODEL_NAME


def get_model(model_name: str | None = None):
    """初始化并返回一个可用的 Gemini 模型对象。"""
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(model_name or MODEL_NAME)
    return model
