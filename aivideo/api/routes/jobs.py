from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
import yaml

from aivideo.api.schemas import (
    CreateJobRequest,
    RecutJobRequest,
    UpdateJobRequest,
    JobDetail,
    JobProgress,
    JobSummary,
    AnalyzeAnchorsRequest,
    AnalyzeAnchorsResponse,
    JobVisualAnchorsResponse,
    UpdateVisualAnchorsRequest,
    GenerateHeroAnchorResponse,
    CharacterAnchor,
    CharacterAnchorDraft,
    AddCharacterRequest,
    PatchCharacterRequest,
)
from aivideo.story_generator import (
    create_job_bundle,
    extract_story_visual_anchors,
    parse_script_lines_to_scenes,
    regenerate_job_scene_prompts,
    load_style_presets,
    DEFAULT_STYLE_PRESETS,
)
from aivideo.gemini_image import generate_image
from aivideo.visual_anchors import (
    attach_legacy_hero_to_first,
    build_character_hero_prompt,
    character_has_image,
    character_image_path,
    character_image_url,
    clear_all_character_images,
    compose_subject_anchor,
    ensure_characters,
    first_hero_url,
    invalidate_changed_character_images,
    legacy_hero_path,
    normalize_characters,
    persist_characters_on_anchors,
    prune_character_images,
)

router = APIRouter(prefix="/jobs", tags=["專案管理"])
REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_DIR = REPO_ROOT / "jobs"


def _job_yaml_path(job_dir: Path) -> Path:
    return job_dir / "job.yaml"


def _load_job_cfg(job_dir: Path) -> dict:
    from aivideo.job_files import load_job_config

    path = _job_yaml_path(job_dir)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="找不到 job.yaml")
    return load_job_config(job_dir)


def _save_job_cfg(job_dir: Path, cfg: dict) -> None:
    from aivideo.job_files import save_job_config

    save_job_config(job_dir, cfg)


def _ensure_visual_anchors(cfg: dict) -> dict:
    if "visual_anchors" not in cfg or not isinstance(cfg["visual_anchors"], dict):
        cfg["visual_anchors"] = {}
    return cfg["visual_anchors"]


def _style_prefix(cfg: dict) -> str:
    img = cfg.get("image") if isinstance(cfg.get("image"), dict) else {}
    style_key = img.get("style") or cfg.get("style") or "otomo_katsuhiro"
    all_styles = load_style_presets()
    style_info = all_styles.get(style_key) or DEFAULT_STYLE_PRESETS.get("otomo_katsuhiro", {})
    return str(style_info.get("prefix") or cfg.get("style_prefix") or "").strip()


def _serialize_characters(job_id: str, job_dir: Path, characters: list[dict[str, str]]) -> list[CharacterAnchor]:
    attach_legacy_hero_to_first(job_dir, characters)
    out: list[CharacterAnchor] = []
    for ch in characters:
        cid = ch["id"]
        out.append(
            CharacterAnchor(
                id=cid,
                name=ch.get("name") or cid,
                appearance=ch.get("appearance") or "",
                entity_type=ch.get("entity_type", "character"),
                has_image=character_has_image(job_dir, cid),
                image_url=character_image_url(job_id, cid, job_dir),
            )
        )
    return out


def _anchors_response(job_id: str, job_dir: Path, cfg: dict | None = None) -> JobVisualAnchorsResponse:
    cfg = cfg if cfg is not None else _load_job_cfg(job_dir)
    v_anchors = cfg.get("visual_anchors", {})
    if not isinstance(v_anchors, dict):
        v_anchors = {}
    characters = ensure_characters(v_anchors)
    has_hero, hero_url = first_hero_url(job_id, job_dir, characters)
    return JobVisualAnchorsResponse(
        subject=v_anchors.get("subject") or compose_subject_anchor(characters),
        environment=v_anchors.get("environment", ""),
        use_image_reference=bool(v_anchors.get("use_image_reference", True)),
        has_hero_image=has_hero,
        hero_image_url=hero_url,
        characters=_serialize_characters(job_id, job_dir, characters),
    )


def _generate_one_character_sheet(job_dir: Path, cfg: dict, character: dict[str, str]) -> Path:
    v_anchors = cfg.get("visual_anchors", {}) if isinstance(cfg.get("visual_anchors"), dict) else {}
    environment = v_anchors.get("environment") or "lighting and materials matching the project art style, 16:9 widescreen"
    dest = character_image_path(job_dir, character["id"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_character_hero_prompt(
        style_prefix=_style_prefix(cfg),
        name=character.get("name") or character["id"],
        appearance=character.get("appearance") or character.get("name") or "distinct character",
        environment=str(environment),
        entity_type=character.get("entity_type", "character"),
    )
    from aivideo.naming import DEFAULT_IMAGE_MODEL

    image_cfg = cfg.get("image") if isinstance(cfg.get("image"), dict) else {}
    img_model = str(image_cfg.get("model") or "").strip() or DEFAULT_IMAGE_MODEL
    generate_image(
        prompt=prompt,
        dest=dest,
        aspect_ratio="16:9",
        image_size="1K",
        model=img_model,
    )
    return dest


def _calculate_job_progress(job_dir: Path) -> JobProgress:
    from aivideo.naming import is_film_stale, is_scene_visual_ready

    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return JobProgress()

    scene_dirs = sorted([d for d in scenes_dir.iterdir() if d.is_dir()])
    total_scenes = len(scene_dirs)
    images_ready = sum(1 for d in scene_dirs if is_scene_visual_ready(d))
    audio_ready = sum(1 for d in scene_dirs if (d / "speech.wav").is_file())
    film_file = job_dir / "compose" / "film.mp4"
    film_ready = film_file.is_file()
    film_mtime = int(film_file.stat().st_mtime) if film_ready else 0
    film_stale = is_film_stale(job_dir) if film_ready else False

    # 計算已生成語音時長與全片預估成片總時長
    total_audio_sec = 0.0
    for d in scene_dirs:
        sp_json = d / "speech.json"
        if sp_json.is_file():
            try:
                data = json.loads(sp_json.read_text(encoding="utf-8"))
                for k in ("duration_sec", "duration"):
                    if data.get(k) is not None:
                        val = float(data[k])
                        if val > 0.05:
                            total_audio_sec += val
                            break
            except Exception:
                pass

    total_audio_sec = round(total_audio_sec, 2)
    if total_scenes > 0:
        if audio_ready == total_scenes and total_audio_sec > 0:
            estimated_duration_sec = total_audio_sec
        elif audio_ready > 0 and total_audio_sec > 0:
            avg_sec = total_audio_sec / audio_ready
            estimated_duration_sec = round(total_audio_sec + avg_sec * (total_scenes - audio_ready), 2)
        else:
            estimated_duration_sec = round(total_scenes * 5.5, 2)
    else:
        estimated_duration_sec = 0.0

    yt_published = False
    yt_id = None
    yt_url = None
    yt_uploaded_at = None

    yt_file = job_dir / "compose" / "youtube.json"
    if yt_file.is_file():
        try:
            with open(yt_file, "r", encoding="utf-8") as f:
                ydata = json.load(f)
            if ydata.get("video_id"):
                yt_published = True
                yt_id = ydata.get("video_id")
                yt_url = ydata.get("video_url")
                yt_uploaded_at = ydata.get("uploaded_at")
        except Exception:
            pass

    return JobProgress(
        scenes_count=total_scenes,
        images_ready=images_ready,
        audio_ready=audio_ready,
        film_ready=film_ready,
        film_stale=film_stale,
        film_mtime=film_mtime,
        youtube_published=yt_published,
        youtube_video_id=yt_id,
        youtube_video_url=yt_url,
        youtube_uploaded_at=yt_uploaded_at,
        total_audio_sec=total_audio_sec,
        estimated_duration_sec=estimated_duration_sec,
    )


def _to_job_summary(job_dir: Path, data: dict | None = None) -> JobSummary:
    from aivideo.naming import job_use_pip

    if data is None:
        path = _job_yaml_path(job_dir)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.is_file() else {}
    img = data.get("image") if isinstance(data.get("image"), dict) else {}
    sub = data.get("subtitle") if isinstance(data.get("subtitle"), dict) else {}
    burn_sub = str(sub.get("mode", "none")).strip().lower() == "hard"
    mtime = datetime.fromtimestamp(job_dir.stat().st_mtime, tz=timezone.utc).isoformat()
    return JobSummary(
        id=job_dir.name,
        title=data.get("title", job_dir.name),
        language=data.get("language", "zh-Hant"),
        voice_id=data.get("voice_id", "tw_female01"),
        style_id=img.get("style"),
        image_model=img.get("model"),
        use_pip=job_use_pip(data),
        burn_subtitles=burn_sub,
        visual_pacing=str(data.get("visual_pacing") or "balanced"),
        progress=_calculate_job_progress(job_dir),
        updated_at=mtime,
    )


@router.get("", response_model=List[JobSummary])
def list_jobs() -> List[JobSummary]:
    if not JOBS_DIR.is_dir():
        return []

    results: List[JobSummary] = []
    job_dirs = sorted(
        [d for d in JOBS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for jdir in job_dirs:
        try:
            results.append(_to_job_summary(jdir))
        except Exception as exc:
            detail = getattr(exc, "detail", None)
            message = detail.strip() if isinstance(detail, str) and detail.strip() else (str(exc).strip() or "讀取失敗")
            results.append(
                JobSummary(
                    id=jdir.name,
                    title=jdir.name,
                    progress=JobProgress(),
                    load_error=message,
                )
            )
    return results


@router.get("/{job_id}", response_model=JobDetail)
def get_job_detail(job_id: str) -> JobDetail:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"找不到專案 {job_id}")

    from aivideo.job_files import load_job_config

    config: Dict[str, Any] = {}
    try:
        config = load_job_config(job_dir)
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

    custom_prompt = config.get("custom_prompt") or None
    outline = config.get("outline") or None

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
        custom_prompt=custom_prompt,
        outline=outline,
    )


@router.post("", response_model=JobSummary)
def create_job(req: CreateJobRequest) -> JobSummary:
    from aivideo.naming import build_job_id, resolve_unique_job_id

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = resolve_unique_job_id(JOBS_DIR, build_job_id(req.topic, req.slug))
    job_dir = JOBS_DIR / job_id

    # 決定視覺錨點：前端已確認的角色／環境優先，否則自動分析
    provided_characters = normalize_characters(
        [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in (req.characters or [])]
    )
    has_env = bool(req.environment_anchor and req.environment_anchor.strip())
    has_subject = bool(req.subject_anchor and req.subject_anchor.strip())
    if provided_characters and has_env:
        characters = provided_characters
        env_anchor = req.environment_anchor.strip()
        subject_anchor = compose_subject_anchor(characters) or (req.subject_anchor or "").strip()
    elif has_subject and has_env:
        env_anchor = req.environment_anchor.strip()
        subject_anchor = req.subject_anchor.strip()
        characters = provided_characters or normalize_characters(
            [{"id": "main", "name": "Main Subject", "appearance": subject_anchor}]
        )
    else:
        anchors_dict = extract_story_visual_anchors(
            topic=req.topic, script_text=req.script, style_key=req.style_id
        )
        characters = normalize_characters(anchors_dict.get("characters"))
        subject_anchor = str(anchors_dict.get("subject_anchor", "") or compose_subject_anchor(characters))
        env_anchor = str(anchors_dict.get("environment_anchor", ""))
        if provided_characters:
            characters = provided_characters
            subject_anchor = compose_subject_anchor(characters) or subject_anchor

    # 拆解分鏡（依據選定之視覺風格產生各幕英文 Prompt）
    scenes_data = parse_script_lines_to_scenes(
        script_lines_text=req.script,
        visual_pacing=req.visual_pacing,
        style_key=req.style_id,
        subject_anchor=subject_anchor,
        environment_anchor=env_anchor,
        topic=req.topic,
        characters=characters,
        outline=req.outline,
    )

    created_dir = create_job_bundle(
        job_id=job_id,
        title=req.topic,
        scenes=scenes_data,
        style_key=req.style_id,
        voice_id=req.voice_id,
        subject_anchor=subject_anchor,
        environment_anchor=env_anchor,
        characters=characters,
        image_model=req.image_model,
        custom_prompt=req.custom_prompt,
        outline=req.outline,
        tone_id=req.tone_id,
        use_pip=req.use_pip,
        script_text=req.script,
        visual_pacing=req.visual_pacing,
    )

    return _to_job_summary(created_dir)


from aivideo.api.routes.anchors import (
    add_character_anchor,
    analyze_script_anchors,
    delete_character_anchor,
    delete_character_hero,
    delete_hero_anchor,
    generate_character_hero,
    generate_hero_anchor,
    get_job_anchors,
    patch_character_anchor,
    sync_job_prompts,
    update_job_anchors,
    upload_character_hero,
    upload_hero_anchor,
)


@router.patch("/{job_id}", response_model=JobSummary)
def update_job(job_id: str, req: UpdateJobRequest) -> JobSummary:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    job_yaml_path = job_dir / "job.yaml"
    if not job_yaml_path.is_file():
        raise HTTPException(status_code=404, detail="找不到 job.yaml")

    data = _load_job_cfg(job_dir)

    if req.title is not None:
        data["title"] = req.title
    if req.voice_id is not None:
        data["voice_id"] = req.voice_id
    if req.image_model is not None:
        if "image" not in data or not isinstance(data["image"], dict):
            data["image"] = {}
        data["image"]["model"] = req.image_model
    if req.style_id is not None:
        if "image" not in data or not isinstance(data["image"], dict):
            data["image"] = {}
        data["image"]["style"] = req.style_id
    if req.tone_id is not None:
        data["tone_id"] = req.tone_id
    if req.visual_pacing is not None:
        data["visual_pacing"] = req.visual_pacing
    if req.custom_prompt is not None:
        data["custom_prompt"] = req.custom_prompt
    if req.outline is not None:
        data["outline"] = req.outline

    if req.script is not None:
        try:
            (job_dir / "script.md").write_text(req.script, encoding="utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"寫入 script.md 失敗: {str(e)}")
    if req.use_pip is not None:
        data["use_pip"] = bool(req.use_pip)
    if req.burn_subtitles is not None:
        if "subtitle" not in data or not isinstance(data["subtitle"], dict):
            data["subtitle"] = {"font_size": 48}
        data["subtitle"]["mode"] = "hard" if req.burn_subtitles else "none"

    # 視覺錨點與角色定裝更新
    if (
        req.characters is not None
        or req.subject_anchor is not None
        or req.environment_anchor is not None
        or req.clear_hero_images
    ):
        v_anchors = _ensure_visual_anchors(data)
        old_chars = ensure_characters(v_anchors)
        if req.environment_anchor is not None:
            v_anchors["environment"] = req.environment_anchor.strip()
        if req.characters is not None:
            norm_chars = normalize_characters(
                [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in req.characters]
            )
            persist_characters_on_anchors(v_anchors, norm_chars)
            if req.clear_hero_images:
                clear_all_character_images(job_dir)
            else:
                invalidate_changed_character_images(job_dir, old_chars, norm_chars)
        elif req.subject_anchor is not None:
            v_anchors["subject"] = req.subject_anchor.strip()
            if not v_anchors.get("characters"):
                norm_chars = normalize_characters(
                    [{"id": "main", "name": "Main Subject", "appearance": req.subject_anchor.strip()}]
                )
                persist_characters_on_anchors(v_anchors, norm_chars)
                if req.clear_hero_images:
                    clear_all_character_images(job_dir)
                else:
                    invalidate_changed_character_images(job_dir, old_chars, norm_chars)
        elif req.clear_hero_images:
            clear_all_character_images(job_dir)
        data["visual_anchors"] = v_anchors

    try:
        _save_job_cfg(job_dir, data)
        if req.outline is not None:
            from aivideo.acts import sync_job_scene_acts

            sync_job_scene_acts(job_dir, data.get("outline"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新專案失敗: {str(e)}")

    return _to_job_summary(job_dir, data)


@router.post("/{job_id}/recut", response_model=JobSummary)
def recut_job(job_id: str, req: RecutJobRequest) -> JobSummary:
    """依目前（或傳入）口白清空舊分鏡與舊成片，重新切分鏡並寫入全新 scene.yaml。"""
    from aivideo.scene_cut import apply_scene_cut
    from aivideo.visual_anchors import compose_subject_anchor, ensure_characters

    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    script = (req.script or "").strip()
    if not script:
        script_path = job_dir / "script.md"
        if script_path.is_file():
            script = script_path.read_text(encoding="utf-8")
    if not script.strip():
        raise HTTPException(status_code=400, detail="沒有可切鏡的口白")

    (job_dir / "script.md").write_text(script, encoding="utf-8")

    # 第一時間先清空舊 scenes 與舊 compose 成片，確保不殘留任何舊圖、舊音或舊分鏡
    scenes_dir = job_dir / "scenes"
    if scenes_dir.is_dir():
        shutil.rmtree(scenes_dir, ignore_errors=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)
    compose_dir = job_dir / "compose"
    if compose_dir.is_dir():
        shutil.rmtree(compose_dir, ignore_errors=True)

    cfg = _load_job_cfg(job_dir)
    v_anchors = cfg.get("visual_anchors", {}) if isinstance(cfg.get("visual_anchors"), dict) else {}
    characters = ensure_characters(v_anchors)
    subject = v_anchors.get("subject") or compose_subject_anchor(characters)
    environment = v_anchors.get("environment") or ""
    style_key = (cfg.get("image") or {}).get("style") or "otomo_katsuhiro"
    title = cfg.get("title") or job_id

    scenes_data = parse_script_lines_to_scenes(
        script_lines_text=script,
        visual_pacing=req.visual_pacing,
        style_key=style_key,
        subject_anchor=subject,
        environment_anchor=environment,
        topic=title,
        characters=characters,
        outline=str(cfg.get("outline") or ""),
    )
    apply_scene_cut(job_dir, scenes_data, clear_existing=True)
    if req.visual_pacing:
        cfg["visual_pacing"] = req.visual_pacing
        _save_job_cfg(job_dir, cfg)
    return _to_job_summary(job_dir, cfg)


@router.post("/{job_id}/clear")
def clear_job_media(job_id: str):
    """
    全部清除/清空已生成素材：
    刪除所有分鏡的已生成圖片 (image.png, image.json, takes/)、語音 (speech.wav, speech.json)、
    考據圖 (pip.png) 與合成目錄 (compose/)，重置 current 狀態，將專案恢復為未出圖未配音的初始分鏡狀態。
    """
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    scenes_dir = job_dir / "scenes"
    cleared_scenes = 0

    if scenes_dir.is_dir():
        for s_dir in scenes_dir.iterdir():
            if not s_dir.is_dir():
                continue
            # 刪除已生成的圖、音、考據圖與 takes
            for fname in ("image.png", "image.json", "speech.wav", "speech.json", "pip.png", "pip.mp4"):
                f = s_dir / fname
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass
            takes_dir = s_dir / "takes"
            if takes_dir.is_dir():
                try:
                    shutil.rmtree(takes_dir)
                except Exception:
                    pass

            # 重置 scene.yaml 內的 current 與 pip.enabled
            s_yaml = s_dir / "scene.yaml"
            if s_yaml.is_file():
                try:
                    scfg = yaml.safe_load(s_yaml.read_text(encoding="utf-8")) or {}
                    scfg["current"] = {"speech_take": None, "image_take": None}
                    if "pip" in scfg and isinstance(scfg["pip"], dict):
                        scfg["pip"]["enabled"] = False
                    s_yaml.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
                except Exception:
                    pass
            cleared_scenes += 1

    # 清空成片合成目錄
    compose_dir = job_dir / "compose"
    if compose_dir.is_dir():
        try:
            shutil.rmtree(compose_dir)
        except Exception:
            pass

    return {
        "success": True,
        "message": f"已成功清除專案 {job_id} 的全部已生成素材（共 {cleared_scenes} 幕重置回待出圖狀態）",
        "cleared_scenes": cleared_scenes,
    }


@router.post("/{job_id}/clear-images")
def clear_job_images(job_id: str):
    """
    僅清空所有分鏡已生成的圖片：
    刪除各分鏡目錄下的 image.png, image.json 以及 takes/ 目錄下的圖片 take (*.png)，
    將 scene.yaml 內的 current.image_take 重置為 None，並清空 compose/ 成片目錄。
    完整保留語音 (speech.wav)、考據圖 (pip.png) 與分鏡台詞腳本。
    """
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    scenes_dir = job_dir / "scenes"
    cleared_scenes = 0

    if scenes_dir.is_dir():
        for s_dir in scenes_dir.iterdir():
            if not s_dir.is_dir():
                continue

            # 刪除根層級圖片與中繼資料
            for fname in ("image.png", "image.json"):
                f = s_dir / fname
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass

            # 刪除 takes 目錄下的所有圖片歷史版本
            takes_dir = s_dir / "takes"
            if takes_dir.is_dir():
                for png_file in takes_dir.glob("*.png"):
                    try:
                        png_file.unlink()
                        # 若對應同名 json 存在且不包含語音資訊，一併清除
                        json_file = png_file.with_suffix(".json")
                        if json_file.is_file():
                            json_file.unlink()
                    except Exception:
                        pass

            # 重置 scene.yaml 內的 image_take
            s_yaml = s_dir / "scene.yaml"
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
            cleared_scenes += 1

    # 清空成片合成目錄（畫面變動後需重新合成）
    compose_dir = job_dir / "compose"
    if compose_dir.is_dir():
        try:
            shutil.rmtree(compose_dir)
        except Exception:
            pass

    return {
        "success": True,
        "message": f"已成功清空專案 {job_id} 的全部已生成圖片（共 {cleared_scenes} 幕重置回待出圖狀態，語音與台詞已完整保留）",
        "cleared_scenes": cleared_scenes,
    }


@router.post("/{job_id}/clear-audio")
def clear_job_audio(job_id: str):
    """
    僅清空所有分鏡已生成的配音：
    刪除各分鏡目錄下的 speech.wav, speech.json 以及 takes/ 目錄下的音訊 take (*.wav 及 speech_*.json)，
    將 scene.yaml 內的 current.speech_take 重置為 None，並清空 compose/ 成片目錄。
    完整保留畫面 (image.png)、考據圖 (pip.png) 與分鏡台詞腳本。
    """
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    scenes_dir = job_dir / "scenes"
    cleared_scenes = 0

    if scenes_dir.is_dir():
        for s_dir in scenes_dir.iterdir():
            if not s_dir.is_dir():
                continue

            # 刪除根層級語音與中繼資料
            for fname in ("speech.wav", "speech.json"):
                f = s_dir / fname
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass

            # 刪除 takes 目錄下的所有語音歷史版本
            takes_dir = s_dir / "takes"
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

            # 重置 scene.yaml 內的 speech_take
            s_yaml = s_dir / "scene.yaml"
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
            cleared_scenes += 1

    # 清空成片合成目錄（音訊變動後需重新合成）
    compose_dir = job_dir / "compose"
    if compose_dir.is_dir():
        try:
            shutil.rmtree(compose_dir)
        except Exception:
            pass

    return {
        "success": True,
        "message": f"已成功清空專案 {job_id} 的全部已生成配音（共 {cleared_scenes} 幕重置回待配音狀態，圖片與台詞已完整保留）",
        "cleared_scenes": cleared_scenes,
    }


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
