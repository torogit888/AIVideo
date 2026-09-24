from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
import yaml

from aivideo.api.schemas import (
    CreateJobRequest,
    UpdateJobRequest,
    JobDetail,
    JobProgress,
    JobSummary,
)
from aivideo.story_generator import (
    create_job_bundle,
    extract_story_visual_anchors,
    parse_script_lines_to_scenes,
)

router = APIRouter(prefix="/jobs", tags=["專案管理"])
REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_DIR = REPO_ROOT / "jobs"


def _calculate_job_progress(job_dir: Path) -> JobProgress:
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return JobProgress()

    scene_dirs = sorted([d for d in scenes_dir.iterdir() if d.is_dir()])
    total_scenes = len(scene_dirs)
    images_ready = sum(1 for d in scene_dirs if (d / "image.png").is_file())
    audio_ready = sum(1 for d in scene_dirs if (d / "speech.wav").is_file() or (d / "audio.wav").is_file())
    film_ready = (job_dir / "compose" / "film.mp4").is_file()

    return JobProgress(
        scenes_count=total_scenes,
        images_ready=images_ready,
        audio_ready=audio_ready,
        film_ready=film_ready,
    )


@router.get("", response_model=List[JobSummary])
def list_jobs() -> List[JobSummary]:
    if not JOBS_DIR.is_dir():
        return []

    results: List[JobSummary] = []
    # 按照資料夾修改時間倒序
    job_dirs = sorted(
        [d for d in JOBS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for jdir in job_dirs:
        job_yaml_path = jdir / "job.yaml"
        title = jdir.name
        voice_id = "female01"
        style_id = None
        lang = "zh-Hant"

        if job_yaml_path.is_file():
            try:
                data = yaml.safe_load(job_yaml_path.read_text(encoding="utf-8")) or {}
                title = data.get("title", title)
                voice_id = data.get("voice_id", voice_id)
                lang = data.get("language", lang)
                style_id = data.get("image", {}).get("style")
            except Exception:
                pass

        mtime = datetime.fromtimestamp(jdir.stat().st_mtime, tz=timezone.utc).isoformat()
        progress = _calculate_job_progress(jdir)

        results.append(
            JobSummary(
                id=jdir.name,
                title=title,
                language=lang,
                voice_id=voice_id,
                style_id=style_id,
                progress=progress,
                updated_at=mtime,
            )
        )
    return results


@router.get("/{job_id}", response_model=JobDetail)
def get_job_detail(job_id: str) -> JobDetail:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"找不到專案 {job_id}")

    job_yaml_path = job_dir / "job.yaml"
    config: Dict[str, Any] = {}
    if job_yaml_path.is_file():
        try:
            config = yaml.safe_load(job_yaml_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            config = {"error": f"讀取 job.yaml 失敗: {str(e)}"}

    title = config.get("title", job_id)
    anchors = config.get("visual_anchors", {})
    anchors_str = None
    if isinstance(anchors, dict) and (anchors.get("subject") or anchors.get("environment")):
        anchors_str = f"主角: {anchors.get('subject', '')} | 場景: {anchors.get('environment', '')}"

    has_script = (job_dir / "script.md").is_file()
    script_content = (job_dir / "script.md").read_text(encoding="utf-8") if has_script else None
    has_film = (job_dir / "compose" / "film.mp4").is_file()

    film_url = f"/media/jobs/{job_id}/compose/film.mp4" if has_film else None
    preview_url = f"/media/jobs/{job_id}/preview.html" if (job_dir / "preview.html").is_file() else None

    return JobDetail(
        id=job_id,
        title=title,
        config=config,
        visual_anchors=anchors_str,
        has_script=has_script,
        script_content=script_content,
        has_film=has_film,
        film_url=film_url,
        preview_html_url=preview_url,
    )


@router.post("", response_model=JobSummary)
def create_job(req: CreateJobRequest) -> JobSummary:
    # 產生合法 slug
    today_str = datetime.now().strftime("%Y%m%d")
    slug = req.slug.strip() if req.slug else ""
    if not slug:
        # 由 topic 生成簡短英文或拼音/主題
        clean_name = re.sub(r"[^\w\s-]", "", req.topic).strip()
        slug = re.sub(r"[-\s]+", "_", clean_name)[:30] or "new_project"
    
    job_id = f"{today_str}_{slug}"
    job_dir = JOBS_DIR / job_id

    # 自動擷取視覺錨點
    subject_anchor, env_anchor = extract_story_visual_anchors(req.script, req.topic)

    # 拆解分鏡
    scenes_data = parse_script_lines_to_scenes(
        script_lines_text=req.script,
        visual_pacing=req.visual_pacing,
        sentences_per_scene=req.lines_per_scene,
        style_key=req.style_id,
        subject_anchor=subject_anchor,
        environment_anchor=env_anchor,
        topic=req.topic,
    )

    created_dir = create_job_bundle(
        job_id=job_id,
        title=req.topic,
        scenes=scenes_data,
        style_key=req.style_id,
        voice_id=req.voice_id,
        subject_anchor=subject_anchor,
        environment_anchor=env_anchor,
    )

    # 同步寫入 script.md
    (created_dir / "script.md").write_text(req.script, encoding="utf-8")

    progress = _calculate_job_progress(created_dir)
    return JobSummary(
        id=job_id,
        title=req.topic,
        voice_id=req.voice_id,
        style_id=req.style_id,
        progress=progress,
    )


@router.patch("/{job_id}", response_model=JobSummary)
def update_job(job_id: str, req: UpdateJobRequest) -> JobSummary:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    job_yaml_path = job_dir / "job.yaml"
    if not job_yaml_path.is_file():
        raise HTTPException(status_code=404, detail="找不到 job.yaml")

    data = yaml.safe_load(job_yaml_path.read_text(encoding="utf-8")) or {}

    if req.title is not None:
        data["title"] = req.title
    if req.voice_id is not None:
        data["voice_id"] = req.voice_id
    if req.style_id is not None:
        if "image" not in data or not isinstance(data["image"], dict):
            data["image"] = {}
        data["image"]["style"] = req.style_id

    try:
        job_yaml_path.write_text(
            yaml.dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新專案失敗: {str(e)}")

    mtime = datetime.fromtimestamp(job_dir.stat().st_mtime, tz=timezone.utc).isoformat()
    progress = _calculate_job_progress(job_dir)
    return JobSummary(
        id=job_id,
        title=data.get("title", job_id),
        language=data.get("language", "zh-Hant"),
        voice_id=data.get("voice_id", "female01"),
        style_id=data.get("image", {}).get("style", "otomo_katsuhiro"),
        progress=progress,
        updated_at=mtime,
    )


@router.delete("/{job_id}")
def delete_job(job_id: str):
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    try:
        shutil.rmtree(job_dir)
        return {"success": True, "deleted_job": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")
