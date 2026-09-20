from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
import yaml

from aivideo.api.schemas import (
    SceneDetail,
    ScenePatchRequest,
    ScenePipConfig,
    SceneStatus,
    SceneSummary,
)
from aivideo.commands.images import run_images
from aivideo.commands.tts import run_tts

router = APIRouter(prefix="/jobs/{job_id}/scenes", tags=["分鏡與右側抽屜"])
REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_DIR = REPO_ROOT / "jobs"


def _get_scene_status(scene_dir: Path, job_id: str) -> SceneStatus:
    img_file = scene_dir / "image.png"
    aud_file = scene_dir / "audio.wav"

    has_img = img_file.is_file()
    has_aud = aud_file.is_file()

    img_url = f"/media/jobs/{job_id}/scenes/{scene_dir.name}/image.png" if has_img else None
    aud_url = f"/media/jobs/{job_id}/scenes/{scene_dir.name}/audio.wav" if has_aud else None

    # 計算音訊秒數
    duration = 0.0
    if has_aud:
        try:
            import wave
            with wave.open(str(aud_file), "r") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    duration = round(frames / float(rate), 2)
        except Exception:
            duration = 6.0
    else:
        duration = 6.0

    return SceneStatus(
        has_image=has_img,
        has_audio=has_aud,
        image_url=img_url,
        audio_url=aud_url,
        duration=duration,
    )


def _load_scene_yaml(scene_dir: Path) -> dict:
    sc_yaml = scene_dir / "scene.yaml"
    if not sc_yaml.is_file():
        raise HTTPException(status_code=404, detail="找不到 scene.yaml")
    try:
        return yaml.safe_load(sc_yaml.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取 scene.yaml 失敗: {str(e)}")


@router.get("", response_model=List[SceneSummary])
def list_scenes(job_id: str) -> List[SceneSummary]:
    job_dir = JOBS_DIR / job_id
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return []

    scene_dirs = sorted([d for d in scenes_dir.iterdir() if d.is_dir()])
    summaries: List[SceneSummary] = []

    for d in scene_dirs:
        try:
            data = _load_scene_yaml(d)
            status = _get_scene_status(d, job_id)
            summaries.append(
                SceneSummary(
                    id=d.name,
                    index=data.get("index", 1),
                    title=data.get("title", d.name),
                    narration=data.get("narration", ""),
                    status=status,
                )
            )
        except Exception:
            continue
    return summaries


@router.get("/{scene_id}", response_model=SceneDetail)
def get_scene_detail(job_id: str, scene_id: str) -> SceneDetail:
    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"找不到分鏡 {scene_id}")

    data = _load_scene_yaml(scene_dir)
    status = _get_scene_status(scene_dir, job_id)

    pip_data = data.get("pip", {}) or {}
    pip_cfg = ScenePipConfig(
        enabled=pip_data.get("enabled", False),
        image=pip_data.get("image"),
        position=pip_data.get("position", "top-right"),
        scale=pip_data.get("scale", 0.35),
        border=pip_data.get("border", 8),
        query=pip_data.get("query"),
        source_title=pip_data.get("source_title"),
        source_url=pip_data.get("source_url"),
    )

    return SceneDetail(
        id=scene_id,
        index=data.get("index", 1),
        title=data.get("title", scene_id),
        narration=data.get("narration", ""),
        image_prompt=data.get("image_prompt", ""),
        image_negative=data.get("image_negative", ""),
        locks=data.get("locks", {"speech": False, "image": False}),
        current=data.get("current", {}),
        pip=pip_cfg,
        status=status,
    )


@router.patch("/{scene_id}", response_model=SceneDetail)
def patch_scene(job_id: str, scene_id: str, req: ScenePatchRequest) -> SceneDetail:
    """右側抽屜局部更新：修改旁白、Prompt、PiP 或鎖定狀態，存檔不觸發全頁刷新"""
    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    yaml_path = scene_dir / "scene.yaml"
    data = _load_scene_yaml(scene_dir)

    if req.title is not None:
        data["title"] = req.title
    if req.narration is not None:
        data["narration"] = req.narration
    if req.image_prompt is not None:
        data["image_prompt"] = req.image_prompt
    if req.image_negative is not None:
        data["image_negative"] = req.image_negative
    if req.locks is not None:
        data["locks"] = req.locks
    if req.pip is not None:
        data["pip"] = req.pip.model_dump()

    try:
        yaml_path.write_text(
            yaml.dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存分鏡失敗: {str(e)}")

    return get_scene_detail(job_id, scene_id)


@router.post("/{scene_id}/image")
def regenerate_scene_image(
    job_id: str,
    scene_id: str,
    background_tasks: BackgroundTasks,
    force: bool = True,
):
    """單幕出圖/重抽"""
    job_dir = JOBS_DIR / job_id
    if not (job_dir / "scenes" / scene_id).is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    # 在背景非同步執行 run_images
    background_tasks.add_task(run_images, job_dir=job_dir, scene=scene_id, force=force)
    return {"message": f"第 {scene_id} 幕生圖任務已啟動", "job_id": job_id, "scene_id": scene_id}


@router.post("/{scene_id}/audio")
def regenerate_scene_audio(
    job_id: str,
    scene_id: str,
    background_tasks: BackgroundTasks,
    force: bool = True,
):
    """單幕語音重錄"""
    job_dir = JOBS_DIR / job_id
    if not (job_dir / "scenes" / scene_id).is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    background_tasks.add_task(run_tts, job_dir=job_dir, scene=scene_id, force=force)
    return {"message": f"第 {scene_id} 幕配音任務已啟動", "job_id": job_id, "scene_id": scene_id}
