"""
统一入口，单一职责：启动 FastAPI 服务。
用法：
- `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- 或直接 `python main.py`
"""

from app.main import app  # 供 uvicorn main:app 使用


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
