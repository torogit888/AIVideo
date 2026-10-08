from __future__ import annotations

import os
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
import requests

from aivideo.api.schemas import (
    CreateVertexAccountRequest,
    ExpandScriptRequest,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    GenerateScriptRequest,
    GenerateScriptResponse,
    ModelsStatusResponse,
    SystemStatusResponse,
    VertexAccountResponse,
)
from aivideo.commands.check import has_gemini_credentials
from aivideo.fonts import resolve_subtitle_font
from aivideo.naming import DEFAULT_VOICE_ID
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

    tones_dir = REPO_ROOT / "assets" / "tones"
    tones = sorted(
        p.stem
        for p in tones_dir.glob("*.md")
        if p.is_file() and p.name.lower() != "readme.md"
    ) if tones_dir.is_dir() else []
    font = resolve_subtitle_font()
    return SystemStatusResponse(
        gemini_configured=gemini_ok,
        comfyui_url=comfy_url,
        comfyui_online=comfy_ok,
        repo_root=str(REPO_ROOT),
        default_voice_id=DEFAULT_VOICE_ID,
        tones=tones,
        font_path=font.get("font_path"),
        font_ok=bool(font.get("ok")),
    )


# ----------------------------------------------------
# Vertex AI 多帳戶/憑證管理
# ----------------------------------------------------
@router.get("/system/accounts", response_model=list[VertexAccountResponse])
def get_vertex_accounts():
    """取得所有已儲存的 Vertex AI / Google 帳戶憑證列表。"""
    from aivideo.credentials_manager import list_accounts
    return list_accounts()


@router.post("/system/accounts", response_model=VertexAccountResponse)
def add_vertex_account(req: CreateVertexAccountRequest):
    """新增 Vertex AI 帳戶憑證（支援 Service Account JSON 檔案內容、或 API Key）。"""
    from aivideo.credentials_manager import create_account
    try:
        acc = create_account(
            name=req.name,
            auth_type=req.auth_type,
            project_id=req.project_id or "",
            location=req.location or "us-central1",
            service_account_json=req.service_account_json,
            api_key=req.api_key,
        )
        return acc
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/system/accounts/{account_id}/activate", response_model=VertexAccountResponse)
def switch_vertex_account(account_id: str):
    """切換並即時啟用指定的 Vertex AI 帳戶憑證。"""
    from aivideo.credentials_manager import activate_account
    try:
        acc = activate_account(account_id)
        return acc
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/system/accounts/{account_id}")
def remove_vertex_account(account_id: str):
    """刪除指定的帳戶憑證。"""
    from aivideo.credentials_manager import delete_account
    try:
        ok = delete_account(account_id)
        if not ok:
            raise HTTPException(status_code=404, detail="找不到該帳戶")
        return {"success": True, "message": "帳戶已刪除"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/system/accounts/{account_id}/test")
def test_vertex_account(account_id: str):
    """測試該帳戶的 Vertex AI / Gemini 連線與可用性。"""
    from aivideo.credentials_manager import activate_account, probe_single_model
    try:
        activate_account(account_id)
        res = probe_single_model("gemini-2.5-flash", model_type="text")
        return res
    except Exception as e:
        return {"status": "error", "message": f"測試失敗: {str(e)}"}


# ----------------------------------------------------
# 各模型可用性與啟用狀態檢測
# ----------------------------------------------------
@router.get("/system/models/status", response_model=ModelsStatusResponse)
def get_models_status():
    """取得當前帳戶下常用文本與生圖模型的可用性與啟用狀態快取。"""
    from aivideo.credentials_manager import check_all_models_status
    return check_all_models_status(force_refresh=False)


@router.post("/system/models/check", response_model=ModelsStatusResponse)
def check_models_availability():
    """立即重新探測當前帳戶下所有文本與生圖模型的可用性與啟用狀態。"""
    from aivideo.credentials_manager import check_all_models_status
    return check_all_models_status(force_refresh=True)


@router.post("/system/check")
def check_connections(target: str = "all"):
    """設定頁檢測：gemini 看憑證，comfy 看 :8188。"""
    want = (target or "all").strip().lower()
    result: dict = {}
    if want in ("all", "gemini"):
        result["gemini_configured"] = has_gemini_credentials()
    if want in ("all", "comfy"):
        comfy_url = os.getenv("COMFY_URL", "http://comfyui:8188").rstrip("/")
        ok = False
        try:
            resp = requests.get(f"{comfy_url}/system_stats", timeout=1.5)
            ok = resp.status_code == 200
        except Exception:
            ok = False
        result["comfyui_online"] = ok
        result["comfyui_url"] = comfy_url
    return result


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
