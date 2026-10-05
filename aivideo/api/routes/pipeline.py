from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from aivideo.api.schemas import PipelineControlResponse, PipelineRunRequest, PipelineStatusResponse
from aivideo.job_files import load_job_config
from aivideo.naming import job_use_pip, should_auto_pip
from aivideo.pipeline_runner import get_pipeline_runner
from aivideo.run_state import load_run_json, persist_runner, snapshot_runner

router = APIRouter(prefix="/pipeline", tags=["流水線批次作業"])
REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_DIR = REPO_ROOT / "jobs"


@router.post("/run", response_model=PipelineStatusResponse)
def run_pipeline(req: PipelineRunRequest) -> PipelineStatusResponse:
    job_dir = JOBS_DIR / req.job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    runner = get_pipeline_runner(req.job_id, job_dir)
    if runner.is_running:
        raise HTTPException(status_code=400, detail="流水線已在執行中，請等待完成或先中止")

    # 執行任務 (mode: "all", "images", "pip", "tts", "compose")
    mode_map = {
        "all": "all",
        "images": "images",
        "pip": "pip",
        "tts": "tts",
        "compose": "compose",
    }
    target_mode = mode_map.get(req.action, "all")

    job_cfg = {}
    try:
        job_cfg = load_job_config(job_dir)
    except Exception:
        job_cfg = {}

    runner.start(
        mode=target_mode,
        skip_done=req.only_missing and not req.force,
        auto_pip=should_auto_pip(req.action, job_use_pip(job_cfg)),
        pause_between_stages=False,
        burn_subtitles=req.burn_subtitles,
    )

    persist_runner(runner)
    snap = snapshot_runner(runner)
    return PipelineStatusResponse(
        is_running=runner.is_running,
        is_paused=runner.is_paused,
        current_job=req.job_id,
        current_action=req.action,
        progress=runner.progress,
        message=runner.status_msg,
        scene_id=snap.get("scene_id"),
        recent_logs=[],
    )


@router.post("/pause", response_model=PipelineControlResponse)
def pause_pipeline(job_id: str):
    job_dir = JOBS_DIR / job_id
    runner = get_pipeline_runner(job_id, job_dir)
    if not runner.is_running:
        return PipelineControlResponse(message="目前無執行中任務", is_running=False, is_paused=False)
    runner.pause()
    persist_runner(runner)
    return PipelineControlResponse(message="已請求暫停", is_running=True, is_paused=True)


@router.post("/resume", response_model=PipelineControlResponse)
def resume_pipeline(job_id: str):
    job_dir = JOBS_DIR / job_id
    runner = get_pipeline_runner(job_id, job_dir)
    if not runner.is_running:
        return PipelineControlResponse(message="目前無執行中任務", is_running=False, is_paused=False)
    runner.resume()
    persist_runner(runner)
    return PipelineControlResponse(message="已繼續", is_running=True, is_paused=False)


@router.post("/stop")
def stop_pipeline(job_id: str):
    job_dir = JOBS_DIR / job_id
    runner = get_pipeline_runner(job_id, job_dir)
    if not runner.is_running:
        return {"message": "目前無執行中任務"}

    runner.stop()
    persist_runner(runner)
    return {"message": "已發送中止請求"}


@router.get("/status", response_model=PipelineStatusResponse)
def get_pipeline_status(job_id: str) -> PipelineStatusResponse:
    job_dir = JOBS_DIR / job_id
    runner = get_pipeline_runner(job_id, job_dir)
    snap = snapshot_runner(runner)
    if not runner.is_running:
        disk = load_run_json(job_dir)
        if disk:
            return PipelineStatusResponse(
                is_running=False,
                is_paused=False,
                current_job=job_id,
                current_action=disk.get("mode"),
                progress=float(disk.get("progress") or 0),
                message=disk.get("message") or ("完成" if disk.get("is_done") else "閒置"),
                scene_id=disk.get("scene_id"),
                recent_logs=[],
            )

    return PipelineStatusResponse(
        is_running=runner.is_running,
        is_paused=runner.is_paused,
        current_job=job_id,
        current_action=runner.mode,
        progress=runner.progress,
        message=runner.status_msg or ("完成" if runner.is_done else "閒置"),
        scene_id=snap.get("scene_id"),
        recent_logs=[],
    )


@router.get("/stream")
async def stream_pipeline_events(request: Request, job_id: str):
    """
    SSE (Server-Sent Events) 端點。
    前端頂列主按鈕與進度條可直接以 EventSource 訂閱此端點，即時接收進度百分比與狀態文字。
    """
    job_dir = JOBS_DIR / job_id

    async def event_generator():
        runner = get_pipeline_runner(job_id, job_dir)

        # 持續串流直到前端斷開或伺服器重載關閉
        try:
            while True:
                if await request.is_disconnected():
                    break

                cur_prog = runner.progress
                cur_msg = runner.status_msg
                is_running = runner.is_running
                is_done = runner.is_done
                error = runner.error_msg

                snap = persist_runner(runner)
                data = {
                    "job_id": job_id,
                    "is_running": is_running,
                    "is_paused": bool(getattr(runner, "is_paused", False)),
                    "is_done": is_done,
                    "progress": round(cur_prog * 100, 1),
                    "message": cur_msg,
                    "error": error,
                    "scene_id": snap.get("scene_id"),
                    "phase": snap.get("phase"),
                    "has_image": snap.get("has_image"),
                    "has_audio": snap.get("has_audio"),
                    "cooldown_remaining": int(getattr(runner, "cooldown_remaining", 0) or 0),
                    "cooldown_total": int(getattr(runner, "cooldown_total", 0) or 0),
                    "notice_seq": int(getattr(runner, "notice_seq", 0) or 0),
                    "notice": getattr(runner, "notice_text", "") or "",
                    "notice_level": getattr(runner, "notice_level", "info") or "info",
                    "timestamp": time.time(),
                }

                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                # 如果已經結束且不再運行，發送最後一次完成事件後休眠較長間隔
                if not is_running and (is_done or error):
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(0.5)
        except (asyncio.CancelledError, GeneratorExit):
            # 伺服器重載或客戶端關閉時平滑退出，避免 Uvicorn 卡死等待
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
