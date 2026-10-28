from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from aivideo.api.routes import anchors, assets, jobs, pipeline, scenes, system, youtube
from aivideo.commands.check import _load_dotenv
from aivideo.media import media_mounts, spa_dist_dir
from aivideo.pipeline_runner import cleanup_stale_run_states, stop_all_pipeline_runners

_load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # 啟動時：自動清除前次因 Reload Window 或重啟而殘留的 is_running 狀態
    cleanup_stale_run_states(REPO_ROOT / "jobs")
    yield
    # 關閉 / 熱重載時：自動停止所有正在跑的背景 Job 執行緒
    stop_all_pipeline_runners()


app = FastAPI(
    title="AIVideo Studio API",
    description="說書人影片合成與分鏡創作 Studio 後端 API 服務",
    version="1.0.0",
    lifespan=_lifespan,
)

# 跨域配置：允許現代前端開發環境（Vite localhost:5173 / Next.js localhost:3000 等）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊 API 路由（統一加上 /api/v1 前綴）
api_v1_prefix = "/api/v1"
app.include_router(system.router, prefix=api_v1_prefix)
app.include_router(jobs.router, prefix=api_v1_prefix)
app.include_router(anchors.router, prefix=api_v1_prefix)
app.include_router(scenes.router, prefix=api_v1_prefix)
app.include_router(pipeline.router, prefix=api_v1_prefix)
app.include_router(assets.router, prefix=api_v1_prefix)
app.include_router(youtube.router, prefix=api_v1_prefix)

for mount_url, mount_dir in media_mounts(REPO_ROOT):
    app.mount(mount_url, StaticFiles(directory=str(mount_dir)), name=mount_url.strip("/").replace("/", "_"))


@app.get("/api")
def api_root():
    return {
        "service": "AIVideo Studio API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "ready",
    }


_spa = spa_dist_dir(REPO_ROOT)
if _spa is not None:
    app.mount("/", StaticFiles(directory=str(_spa), html=True), name="studio")
else:

    @app.get("/")
    def root():
        return {
            "service": "AIVideo Studio API",
            "version": "1.0.0",
            "docs": "/docs",
            "status": "ready",
            "studio": "http://localhost:5173",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("aivideo.api.app:app", host="0.0.0.0", port=8000, reload=True)

