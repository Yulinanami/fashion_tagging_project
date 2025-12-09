import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import auth, health, tagging, weather, outfits, tryon
from app.config import TRYON_RESULT_DIR


def create_app() -> FastAPI:
    app = FastAPI(title="Fashion Tagging API")

    # 允许 Android 调用（本地/局域网都放开）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由注册
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tagging.router)
    app.include_router(weather.router)
    app.include_router(outfits.router)
    app.include_router(tryon.router)

    # 静态文件（换装结果等）
    static_root = Path("static")
    static_root.mkdir(parents=True, exist_ok=True)
    Path(TRYON_RESULT_DIR).mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_root), name="static")

    @app.on_event("startup")
    def on_startup():
        init_db()
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    return app


app = create_app()
