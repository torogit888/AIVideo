from __future__ import annotations

import os
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
import requests

from aivideo.api.schemas import (
    ExpandScriptRequest,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    GenerateScriptRequest,
    GenerateScriptResponse,
    SystemStatusResponse,
)
from aivideo.commands.check import has_gemini_credentials
from aivideo.story_generator import (
    expand_story_script,
    generate_story_outline,
    generate_story_script,
)

router = APIRouter(tags=["系統與腳本"])
REPO_ROOT = Path(__file__).resolve().parents[3]


@router.get("/system/status", response_model=SystemStatusResponse)
def get_system_status() -> SystemStatusResponse:
    gemini_ok = has_gemini_credentials()
    comfy_url = os.getenv("COMFY_URL", "http://comfyui:8188").rstrip("/")
    comfy_ok = False
    try:
        resp = requests.get(f"{comfy_url}/system_stats", timeout=1.5)
        comfy_ok = (resp.status_code == 200)
    except Exception:
        comfy_ok = False

    return SystemStatusResponse(
        gemini_configured=gemini_ok,
        comfyui_url=comfy_url,
        comfyui_online=comfy_ok,
        repo_root=str(REPO_ROOT),
    )


@router.post("/script/generate-outline", response_model=GenerateOutlineResponse)
def generate_outline(req: GenerateOutlineRequest) -> GenerateOutlineResponse:
    try:
        outline = generate_story_outline(
            topic=req.topic,
            tone_id=req.tone_id,
            model=req.model,
            user_prompt=req.user_prompt,
        )
        return GenerateOutlineResponse(outline=outline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"大綱生成失敗: {str(e)}")


@router.post("/script/generate", response_model=GenerateScriptResponse)
def generate_script(req: GenerateScriptRequest) -> GenerateScriptResponse:
    try:
        raw_script = generate_story_script(
            topic=req.topic,
            tone_id=req.tone_id,
            word_count=req.word_count,
            search_grounding=req.internet_search,
            model=req.model,
            notes=req.notes,
            user_prompt=req.user_prompt,
        )
        # 清理並統計字數與估算秒數 (中文語速約每分鐘 200~240 字)
        lines = [line.strip() for line in raw_script.splitlines() if line.strip()]
        total_chars = sum(len(line) for line in lines)
        estimated_scenes = max(1, len(lines) // 2)
        estimated_seconds = int(total_chars / 3.6)

        return GenerateScriptResponse(
            script=raw_script,
            word_count=total_chars,
            estimated_scenes=estimated_scenes,
            estimated_seconds=estimated_seconds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"腳本生成失敗: {str(e)}")


@router.post("/script/expand", response_model=GenerateScriptResponse)
def expand_script(req: ExpandScriptRequest) -> GenerateScriptResponse:
    try:
        raw_script = expand_story_script(
            current_script=req.script,
            topic=req.topic or "",
            tone_id=req.tone_id,
            target_word_count=req.target_word_count,
            model=req.model,
        )
        lines = [line.strip() for line in raw_script.splitlines() if line.strip()]
        total_chars = sum(len(line) for line in lines)
        estimated_scenes = max(1, len(lines) // 2)
        estimated_seconds = int(total_chars / 3.6)

        return GenerateScriptResponse(
            script=raw_script,
            word_count=total_chars,
            estimated_scenes=estimated_scenes,
            estimated_seconds=estimated_seconds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"腳本擴寫失敗: {str(e)}")
