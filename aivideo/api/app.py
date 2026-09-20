from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from aivideo.api.routes import assets, jobs, pipeline, scenes, system
from aivideo.commands.check import _load_dotenv

_load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(
    title="AIVideo Studio API",
    description="說書人影片合成與分鏡創作 Studio 後端 API 服務",
    version="1.0.0",
)

# 跨域配置：允許現代前端開發環境（Vite localhost:5173 / Next.js localhost:3000 等）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊 API 路由（統一加上 /api/v1 前綴）
api_v1_prefix = "/api/v1"
app.include_router(system.router, prefix=api_v1_prefix)
app.include_router(jobs.router, prefix=api_v1_prefix)
app.include_router(scenes.router, prefix=api_v1_prefix)
app.include_router(pipeline.router, prefix=api_v1_prefix)
app.include_router(assets.router, prefix=api_v1_prefix)

# 掛載靜態媒體目錄，直接支援圖片預覽與影片串流播放
if REPO_ROOT.is_dir():
    app.mount("/media", StaticFiles(directory=str(REPO_ROOT)), name="media")


@app.get("/")
def root():
    return {
        "service": "AIVideo Studio API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "ready",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("aivideo.api.app:app", host="0.0.0.0", port=8000, reload=True)

