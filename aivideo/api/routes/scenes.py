from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
import yaml

from aivideo.api.schemas import (
    ApplyPipUrlRequest,
    FetchScenePipRequest,
    GcTakesRequest,
    PipCandidateItem,
    PipCandidatesResponse,
    SceneDetail,
    ScenePatchRequest,
    ScenePipConfig,
    SceneStatus,
    SceneSummary,
    SceneTake,
    SceneTakes,
    SelectTakeRequest,
    TranslatePromptRequest,
    TranslatePromptResponse,
)
from aivideo.commands.images import run_images
from aivideo.commands.tts import run_tts
from aivideo.pipeline_runner import CmdArgs

router = APIRouter(prefix="/jobs/{job_id}/scenes", tags=["分鏡與右側抽屜"])
REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_DIR = REPO_ROOT / "jobs"


def _audio_duration_sec(scene_dir: Path, aud_file: Path) -> float:
    """優先讀 speech.json 的 duration_sec（TTS 寫入的真實時長），再退回 wave / ffprobe。"""
    sp_json = scene_dir / "speech.json"
    if sp_json.is_file():
        try:
            import json

            data = json.loads(sp_json.read_text(encoding="utf-8"))
            for key in ("duration_sec", "duration"):
                if data.get(key) is None:
                    continue
                d = float(data[key])
                if d > 0.05:
                    return round(d, 2)
        except Exception:
            pass
    try:
        import wave

        with wave.open(str(aud_file), "r") as wf:
            rate = wf.getframerate()
            if rate > 0:
                d = wf.getnframes() / float(rate)
                if d > 0.05:
                    return round(d, 2)
    except Exception:
        pass
    try:
        import subprocess

        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(aud_file),
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        d = float((proc.stdout or "").strip())
        if d > 0.05:
            return round(d, 2)
    except Exception:
        pass
    return 6.0


def _get_scene_status(scene_dir: Path, job_id: str) -> SceneStatus:
    img_file = scene_dir / "image.png"
    aud_file = scene_dir / "speech.wav"
    if not aud_file.is_file():
        aud_file = scene_dir / "audio.wav"
    pip_file = scene_dir / "pip.png"

    has_aud = aud_file.is_file()
    has_pip = pip_file.is_file()

    # 檢查是否為黑底歷史聚焦 (spotlight) 且已有真實考據圖
    is_spotlight = False
    s_yaml_p = scene_dir / "scene.yaml"
    if s_yaml_p.is_file():
        try:
            sc_data = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
            p_mode = str(sc_data.get("pip", {}).get("mode", "")).lower()
            if p_mode in ("spotlight", "focus", "black_bg", "fullscreen") and has_pip:
                is_spotlight = True
        except Exception:
            pass

    has_img = img_file.is_file() or is_spotlight

    img_mtime = int(img_file.stat().st_mtime) if img_file.is_file() else 0
    aud_mtime = int(aud_file.stat().st_mtime) if has_aud else 0
    pip_mtime = int(pip_file.stat().st_mtime) if has_pip else 0

    import urllib.parse
    job_id_encoded = urllib.parse.quote(job_id)

    img_url = f"/media/jobs/{job_id_encoded}/scenes/{scene_dir.name}/image.png?t={img_mtime}" if img_file.is_file() else (
        f"/media/jobs/{job_id_encoded}/scenes/{scene_dir.name}/pip.png?t={pip_mtime}" if is_spotlight else None
    )
    aud_url = f"/media/jobs/{job_id_encoded}/scenes/{scene_dir.name}/{aud_file.name}?t={aud_mtime}" if has_aud else None
    pip_url = f"/media/jobs/{job_id_encoded}/scenes/{scene_dir.name}/pip.png?t={pip_mtime}" if has_pip else None

    duration = _audio_duration_sec(scene_dir, aud_file) if has_aud else 0.0

    return SceneStatus(
        has_image=has_img,
        has_audio=has_aud,
        has_pip=has_pip,
        image_url=img_url,
        audio_url=aud_url,
        pip_url=pip_url,
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


def _scene_takes(scene_dir: Path, job_id: str, scene_id: str) -> SceneTakes:
    from aivideo.takes import list_scene_takes

    raw = list_scene_takes(scene_dir, job_id=job_id, scene_id=scene_id)
    return SceneTakes(
        images=[SceneTake(**t) for t in raw["images"]],
        speeches=[SceneTake(**t) for t in raw["speeches"]],
    )


@router.get("", response_model=List[SceneSummary])
def list_scenes(job_id: str) -> List[SceneSummary]:
    job_dir = JOBS_DIR / job_id
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return []

    scene_dirs = sorted([d for d in scenes_dir.iterdir() if d.is_dir()])
    summaries: List[SceneSummary] = []
    loaded: list[tuple] = []
    for d in scene_dirs:
        try:
            loaded.append((d, _load_scene_yaml(d)))
        except Exception:
            continue

    from aivideo.acts import acts_from_job, assign_acts

    need_acts = any(not int(data.get("act_index") or 0) for _d, data in loaded)
    inferred = []
    if need_acts:
        inferred = assign_acts(len(loaded), acts_from_job(job_dir))

    for i, (d, data) in enumerate(loaded):
        try:
            status = _get_scene_status(d, job_id)
            pip_data = data.get("pip", {}) if isinstance(data.get("pip"), dict) else {}
            pip_query = pip_data.get("query")
            pip_error = str(pip_data.get("fetch_error") or "").strip() or None
            act_index = int(data.get("act_index") or 0)
            act_title = str(data.get("act_title") or "")
            if (not act_index) and inferred:
                act_index = int(inferred[i]["index"])
                act_title = str(inferred[i]["title"])
            locks = data.get("locks") if isinstance(data.get("locks"), dict) else {}
            summaries.append(
                SceneSummary(
                    id=d.name,
                    index=data.get("index", 1),
                    title=data.get("title", d.name),
                    narration=data.get("narration", ""),
                    act_index=act_index,
                    act_title=act_title,
                    pip_query=pip_query,
                    has_pip=status.has_pip,
                    pip_enabled=bool(pip_data.get("enabled", False)),
                    pip_mode=pip_data.get("mode", "pip"),
                    pip_error=None if status.has_pip else pip_error,
                    locks={"image": bool(locks.get("image", False)), "speech": bool(locks.get("speech", False))},
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
        position=pip_data.get("position", "right-center"),
        mode=pip_data.get("mode", "pip"),
        scale=pip_data.get("scale", 0.24),
        border=pip_data.get("border", 5),
        query=pip_data.get("query"),
        source_title=pip_data.get("source_title"),
        source_url=pip_data.get("source_url"),
        fetch_error=None if status.has_pip else (str(pip_data.get("fetch_error") or "").strip() or None),
        verified=bool(pip_data.get("verified", False)),
        review_reason=pip_data.get("review_reason"),
    )

    return SceneDetail(
        id=scene_id,
        index=data.get("index", 1),
        title=data.get("title", scene_id),
        narration=data.get("narration", ""),
        image_prompt=data.get("image_prompt", ""),
        image_negative=data.get("image_negative", ""),
        act_index=int(data.get("act_index") or 0),
        act_title=str(data.get("act_title") or ""),
        locks=data.get("locks", {"speech": False, "image": False}),
        current=data.get("current", {}),
        pip=pip_cfg,
        status=status,
        takes=_scene_takes(scene_dir, job_id, scene_id),
    )


@router.get("/{scene_id}/takes", response_model=SceneTakes)
def get_scene_takes(job_id: str, scene_id: str) -> SceneTakes:
    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"找不到分鏡 {scene_id}")
    return _scene_takes(scene_dir, job_id, scene_id)


@router.post("/{scene_id}/takes/select", response_model=SceneDetail)
def select_scene_take(job_id: str, scene_id: str, req: SelectTakeRequest) -> SceneDetail:
    from aivideo.takes import select_current_take

    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"找不到分鏡 {scene_id}")
    try:
        select_current_take(scene_dir, req.take_id, req.kind)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return get_scene_detail(job_id, scene_id)


@router.post("/{scene_id}/takes/gc")
def gc_scene_takes_route(job_id: str, scene_id: str, req: Optional[GcTakesRequest] = None):
    from aivideo.takes import gc_scene_takes

    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"找不到分鏡 {scene_id}")
    keep = req.keep if req else 3
    return gc_scene_takes(scene_dir, keep=keep)


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


@router.post("/{scene_id}/translate-prompt", response_model=TranslatePromptResponse)
def translate_scene_prompt_route(job_id: str, scene_id: str, req: TranslatePromptRequest) -> TranslatePromptResponse:
    """依據專案全域視覺風格與視覺錨點，將本幕中文口白轉譯為具備高度畫面感的專業英文出圖提示詞。"""
    job_dir = JOBS_DIR / job_id
    scene_dir = job_dir / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    from aivideo.job_files import load_job_config
    from aivideo.story_generator import translate_single_scene_prompt
    from aivideo.visual_anchors import ensure_characters

    jcfg = load_job_config(job_dir)
    scfg = _load_scene_yaml(scene_dir)

    narr = (req.narration or scfg.get("narration") or "").strip()
    if not narr:
        raise HTTPException(status_code=400, detail="本幕尚無口白台詞可供轉譯")

    v_anchors = jcfg.get("visual_anchors", {}) if isinstance(jcfg.get("visual_anchors"), dict) else {}
    characters = ensure_characters(v_anchors)
    sub = v_anchors.get("subject", "")
    env = v_anchors.get("environment", "")
    style_key = (jcfg.get("image") or {}).get("style") or jcfg.get("style") or "otomo_katsuhiro"

    new_prompt = translate_single_scene_prompt(
        narration=narr,
        style_key=style_key,
        subject_anchor=sub,
        environment_anchor=env,
        characters=characters,
    )

    if not new_prompt:
        raise HTTPException(status_code=500, detail="AI 視覺轉譯失敗，請稍後重試")

    return TranslatePromptResponse(
        image_prompt=new_prompt,
    )


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
    cmd_args = CmdArgs(job=job_dir, scene=scene_id, force=force, new_seed=True)
    background_tasks.add_task(run_images, cmd_args)
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

    cmd_args = CmdArgs(job=job_dir, scene=scene_id, force=force)
    background_tasks.add_task(run_tts, cmd_args)
    return {"message": f"第 {scene_id} 幕配音任務已啟動", "job_id": job_id, "scene_id": scene_id}


@router.post("/{scene_id}/pip")
def fetch_scene_pip(job_id: str, scene_id: str, req: Optional[FetchScenePipRequest] = None):
    """為單一分鏡檢索並下載考據照片 (pip.png)，支援傳入自訂檢索詞覆蓋。"""
    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    custom_q = req.query.strip() if (req and req.query and req.query.strip()) else None
    from aivideo.auto_pip import fetch_single_scene_pip
    ok = fetch_single_scene_pip(scene_dir, query=custom_q)
    if not ok:
        raise HTTPException(status_code=400, detail="未檢索到合適考據照片或未指定檢索詞")
    return {"message": "考據照片已成功下載並套用", "job_id": job_id, "scene_id": scene_id}


@router.post("/{scene_id}/pip/url", response_model=SceneDetail)
def apply_scene_pip_url(job_id: str, scene_id: str, req: ApplyPipUrlRequest):
    """直接依指定的圖片 URL 下載並套用為本幕真實考據照片 (pip.png)。"""
    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    url = (req.url or "").strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="請提供有效的 http(s) 圖片網址")

    from aivideo.auto_pip import _download_image_bytes, _write_pip_yaml
    from PIL import Image
    import io

    content = _download_image_bytes(url)
    if not content:
        raise HTTPException(status_code=400, detail="無法自該網址下載圖片，請檢查網址有效性或防盜鏈設定")

    try:
        img = Image.open(io.BytesIO(content)).convert("RGBA")
        img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        img.save(scene_dir / "pip.png", "PNG")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"圖片解析失敗: {str(e)}")

    scfg = _load_scene_yaml(scene_dir)
    q = req.query or scfg.get("pip", {}).get("query") or req.title or "自訂圖片網址"
    result = {"title": req.title or "自訂圖片網址", "url": url}
    _write_pip_yaml(scene_dir, scfg, q, result, enabled=True)
    return get_scene_detail(job_id, scene_id)


@router.post("/{scene_id}/pip/upload", response_model=SceneDetail)
async def upload_scene_pip_file(job_id: str, scene_id: str, file: UploadFile = File(...)):
    """支援本機直接上傳真實歷史考據照片檔案 (pip.png)。"""
    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上傳檔案為空")

    from aivideo.auto_pip import _write_pip_yaml
    from PIL import Image
    import io

    try:
        img = Image.open(io.BytesIO(content)).convert("RGBA")
        img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        img.save(scene_dir / "pip.png", "PNG")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"圖片格式解析失敗: {str(e)}")

    scfg = _load_scene_yaml(scene_dir)
    filename = file.filename or "本地上傳照片"
    q = scfg.get("pip", {}).get("query") or filename
    result = {"title": filename, "url": f"/media/jobs/{job_id}/scenes/{scene_id}/pip.png"}
    _write_pip_yaml(scene_dir, scfg, q, result, enabled=True)
    return get_scene_detail(job_id, scene_id)


@router.get("/{scene_id}/pip/candidates", response_model=PipCandidatesResponse)
def get_scene_pip_candidates(job_id: str, scene_id: str, query: Optional[str] = None):
    """
    全網跨圖庫（不限版權與公有領域限制，廣泛搜尋新聞歷史照片）檢索真實候選圖片供創作者自由挑選。
    """
    scene_dir = JOBS_DIR / job_id / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    scfg = _load_scene_yaml(scene_dir)
    narr = str(scfg.get("narration") or "")
    search_q = (query or "").strip() or scfg.get("pip", {}).get("query") or ""

    if not search_q and narr:
        from aivideo.story_generator import batch_detect_pip_queries
        detected = batch_detect_pip_queries([narr])
        if detected and detected[0]:
            search_q = detected[0]

    if not search_q:
        raise HTTPException(status_code=400, detail="請輸入欲檢索的實體關鍵字")

    from aivideo.auto_pip import search_all_source_candidates
    candidates = search_all_source_candidates(search_q, limit=8)
    items = []
    for c in candidates:
        raw_u = str(c.get("url") or "")
        if raw_u:
            items.append(
                PipCandidateItem(
                    title=str(c.get("title") or search_q),
                    url=raw_u,
                    source=str(c.get("source") or "全網歷史照片"),
                    width=int(c.get("width") or 0),
                    height=int(c.get("height") or 0),
                )
            )
    return PipCandidatesResponse(query=search_q, candidates=items)


@router.delete("/{scene_id}/image")
def clear_scene_image(job_id: str, scene_id: str):
    """單幕清空已生成圖片，重置為待出圖狀態"""
    job_dir = JOBS_DIR / job_id
    scene_dir = job_dir / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    for fname in ("image.png", "image.json"):
        f = scene_dir / fname
        if f.is_file():
            try:
                f.unlink()
            except Exception:
                pass

    # 清除 takes 下的圖片檔案
    takes_dir = scene_dir / "takes"
    if takes_dir.is_dir():
        for png_file in takes_dir.glob("*.png"):
            try:
                png_file.unlink()
                json_file = png_file.with_suffix(".json")
                if json_file.is_file():
                    json_file.unlink()
            except Exception:
                pass

    # 更新 scene.yaml 中的 current.image_take
    s_yaml = scene_dir / "scene.yaml"
    if s_yaml.is_file():
        try:
            scfg = yaml.safe_load(s_yaml.read_text(encoding="utf-8")) or {}
            if "current" in scfg and isinstance(scfg["current"], dict):
                scfg["current"]["image_take"] = None
            else:
                scfg["current"] = {"speech_take": None, "image_take": None}
            s_yaml.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        except Exception:
            pass

    # 清空成片目錄
    compose_dir = job_dir / "compose"
    if compose_dir.is_dir():
        try:
            shutil.rmtree(compose_dir)
        except Exception:
            pass

    return get_scene_detail(job_id, scene_id)


@router.delete("/{scene_id}/audio")
def clear_scene_audio(job_id: str, scene_id: str):
    """單幕清空已生成語音，重置為待配音狀態"""
    job_dir = JOBS_DIR / job_id
    scene_dir = job_dir / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    for fname in ("speech.wav", "speech.json", "audio.wav"):
        f = scene_dir / fname
        if f.is_file():
            try:
                f.unlink()
            except Exception:
                pass

    # 清除 takes 下的語音檔案
    takes_dir = scene_dir / "takes"
    if takes_dir.is_dir():
        for wav_file in takes_dir.glob("*.wav"):
            try:
                wav_file.unlink()
            except Exception:
                pass
        for j_file in takes_dir.glob("speech_*.json"):
            try:
                j_file.unlink()
            except Exception:
                pass
        for txt_file in takes_dir.glob("*_concat.txt"):
            try:
                txt_file.unlink()
            except Exception:
                pass

    # 更新 scene.yaml 中的 current.speech_take
    s_yaml = scene_dir / "scene.yaml"
    if s_yaml.is_file():
        try:
            scfg = yaml.safe_load(s_yaml.read_text(encoding="utf-8")) or {}
            if "current" in scfg and isinstance(scfg["current"], dict):
                scfg["current"]["speech_take"] = None
            else:
                scfg["current"] = {"speech_take": None, "image_take": None}
            s_yaml.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        except Exception:
            pass

    # 清空成片目錄
    compose_dir = job_dir / "compose"
    if compose_dir.is_dir():
        try:
            shutil.rmtree(compose_dir)
        except Exception:
            pass

    return get_scene_detail(job_id, scene_id)


@router.delete("/{scene_id}/pip")
def clear_scene_pip(job_id: str, scene_id: str):
    """單幕清空考據圖 (pip.png) 並重置考據狀態"""
    job_dir = JOBS_DIR / job_id
    scene_dir = job_dir / "scenes" / scene_id
    if not scene_dir.is_dir():
        raise HTTPException(status_code=404, detail="分鏡不存在")

    pip_file = scene_dir / "pip.png"
    if pip_file.is_file():
        try:
            pip_file.unlink()
        except Exception:
            pass

    # 更新 scene.yaml
    s_yaml = scene_dir / "scene.yaml"
    if s_yaml.is_file():
        try:
            scfg = yaml.safe_load(s_yaml.read_text(encoding="utf-8")) or {}
            pip_dict = scfg.get("pip", {}) if isinstance(scfg.get("pip"), dict) else {}
            pip_dict["enabled"] = False
            pip_dict["image"] = None
            pip_dict["mode"] = "pip"
            pip_dict["source_title"] = None
            pip_dict["source_url"] = None
            pip_dict["fetch_error"] = None
            scfg["pip"] = pip_dict
            s_yaml.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        except Exception:
            pass

    # 清空成片目錄以利重新合成
    compose_dir = job_dir / "compose"
    if compose_dir.is_dir():
        try:
            shutil.rmtree(compose_dir)
        except Exception:
            pass

    return get_scene_detail(job_id, scene_id)


