from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
import yaml

from aivideo.api.schemas import (
    CreateJobRequest,
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
    compose_subject_anchor,
    ensure_characters,
    first_hero_url,
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
    path = _job_yaml_path(job_dir)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="找不到 job.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _save_job_cfg(job_dir: Path, cfg: dict) -> None:
    _job_yaml_path(job_dir).write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


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
    )
    img_model = cfg.get("image", {}).get("model", "gemini-2.5-flash-image")
    generate_image(
        prompt=prompt,
        dest=dest,
        aspect_ratio="16:9",
        image_size="1K",
        model=img_model,
    )
    return dest


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

    # 拆解分鏡
    scenes_data = parse_script_lines_to_scenes(
        script_lines_text=req.script,
        visual_pacing=req.visual_pacing,
        sentences_per_scene=req.lines_per_scene,
        style_key=req.style_id,
        subject_anchor=subject_anchor,
        environment_anchor=env_anchor,
        topic=req.topic,
        characters=characters,
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


@router.post("/analyze-anchors", response_model=AnalyzeAnchorsResponse)
def analyze_script_anchors(req: AnalyzeAnchorsRequest) -> AnalyzeAnchorsResponse:
    """在建立專案前，依據腳本與主題預先深度分析提煉主角/核心物件特徵與環境世界觀基調。"""
    if not req.script.strip():
        raise HTTPException(status_code=400, detail="腳本內容不能為空")
    topic = req.topic.strip() or "故事主體"
    data = extract_story_visual_anchors(
        topic=topic, script_text=req.script, style_key=req.style_id or ""
    )
    characters = normalize_characters(data.get("characters"))
    return AnalyzeAnchorsResponse(
        subject_anchor=str(data.get("subject_anchor", "") or compose_subject_anchor(characters)),
        environment_anchor=str(data.get("environment_anchor", "")),
        characters=[
            CharacterAnchorDraft(id=ch["id"], name=ch["name"], appearance=ch.get("appearance", ""))
            for ch in characters
        ],
    )


@router.get("/{job_id}/anchors", response_model=JobVisualAnchorsResponse)
def get_job_anchors(job_id: str) -> JobVisualAnchorsResponse:
    """取得特定專案的視覺一致性錨點設定與定裝基準圖狀態。"""
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    return _anchors_response(job_id, job_dir)


@router.patch("/{job_id}/anchors", response_model=JobVisualAnchorsResponse)
def update_job_anchors(job_id: str, req: UpdateVisualAnchorsRequest) -> JobVisualAnchorsResponse:
    """更新專案的角色外觀錨點、環境光影錨點或切換定裝圖多模態參考開關。"""
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)

    if req.environment is not None:
        v_anchors["environment"] = req.environment.strip()
    if req.use_image_reference is not None:
        v_anchors["use_image_reference"] = req.use_image_reference
    if req.characters is not None:
        old_ids = {ch["id"] for ch in ensure_characters(v_anchors)}
        characters = normalize_characters(
            [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in req.characters]
        )
        persist_characters_on_anchors(v_anchors, characters)
        prune_character_images(job_dir, [ch["id"] for ch in characters])
        # 舊專案單張 hero 若角色列表已換成多人，不再共用
        if old_ids and {ch["id"] for ch in characters} != old_ids:
            pass
    elif req.subject is not None:
        v_anchors["subject"] = req.subject.strip()
        if not v_anchors.get("characters"):
            persist_characters_on_anchors(
                v_anchors,
                normalize_characters([{"id": "main", "name": "Main Subject", "appearance": req.subject.strip()}]),
            )

    _save_job_cfg(job_dir, cfg)
    return _anchors_response(job_id, job_dir, cfg)


def _find_character(characters: list[dict[str, str]], char_id: str) -> dict[str, str]:
    for ch in characters:
        if ch["id"] == char_id:
            return ch
    raise HTTPException(status_code=404, detail="找不到此角色")


@router.post("/{job_id}/anchors/hero", response_model=GenerateHeroAnchorResponse)
def generate_hero_anchor(job_id: str) -> GenerateHeroAnchorResponse:
    """依專案生圖風格，為每位角色各生成一張 16:9 定裝圖。"""
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    if not characters:
        raise HTTPException(status_code=400, detail="尚未設定任何角色外觀錨點，請先分析腳本或手動新增角色")

    persist_characters_on_anchors(v_anchors, characters)
    v_anchors["use_image_reference"] = True

    generated = 0
    last_error = None
    for ch in characters:
        try:
            _generate_one_character_sheet(job_dir, cfg, ch)
            generated += 1
        except Exception as e:
            last_error = e

    _save_job_cfg(job_dir, cfg)
    has_hero, hero_url = first_hero_url(job_id, job_dir, characters)
    if generated == 0:
        raise HTTPException(status_code=500, detail=f"Gemini 定裝圖生成失敗: {last_error}")
    msg = f"已依專案風格生成 {generated} 張角色定裝圖"
    if last_error and generated < len(characters):
        msg += f"（部分失敗：{last_error}）"
    return GenerateHeroAnchorResponse(
        success=True,
        message=msg,
        hero_image_url=hero_url or "",
        generated_count=generated,
    )


@router.post("/{job_id}/anchors/hero/upload")
async def upload_hero_anchor(job_id: str, file: UploadFile = File(...)):
    """上傳參考圖：若已有角色列表則寫入第一位角色，否則作為舊版單張 hero。"""
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    content = await file.read()
    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    if characters:
        dest = character_image_path(job_dir, characters[0]["id"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        persist_characters_on_anchors(v_anchors, characters)
    else:
        (job_dir / "hero_anchor.png").write_bytes(content)

    v_anchors["use_image_reference"] = True
    _save_job_cfg(job_dir, cfg)
    resp = _anchors_response(job_id, job_dir, cfg)
    return {
        "success": True,
        "message": "定裝參考圖上傳成功",
        "hero_image_url": resp.hero_image_url,
    }


@router.delete("/{job_id}/anchors/hero")
def delete_hero_anchor(job_id: str):
    """移除全部角色定裝圖與舊版單張 hero。"""
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    hero_dest = job_dir / "hero_anchor.png"
    if hero_dest.is_file():
        hero_dest.unlink(missing_ok=True)
    chars_dir = job_dir / "characters"
    if chars_dir.is_dir():
        for path in chars_dir.glob("*.png"):
            path.unlink(missing_ok=True)
    return {"success": True, "message": "已移除所有角色定裝圖"}


@router.post("/{job_id}/anchors/characters", response_model=JobVisualAnchorsResponse)
def add_character_anchor(job_id: str, req: AddCharacterRequest) -> JobVisualAnchorsResponse:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    extra = normalize_characters([{"name": req.name, "appearance": req.appearance}])
    if not extra:
        raise HTTPException(status_code=400, detail="角色名稱不能為空")
    # 避免與既有 id 碰撞
    existing = {ch["id"] for ch in characters}
    for ch in extra:
        if ch["id"] in existing:
            ch["id"] = f"{ch['id']}_{len(characters) + 1}"
        characters.append(ch)
    persist_characters_on_anchors(v_anchors, characters)
    _save_job_cfg(job_dir, cfg)
    return _anchors_response(job_id, job_dir, cfg)


@router.patch("/{job_id}/anchors/characters/{char_id}", response_model=JobVisualAnchorsResponse)
def patch_character_anchor(job_id: str, char_id: str, req: PatchCharacterRequest) -> JobVisualAnchorsResponse:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    ch = _find_character(characters, char_id)
    if req.name is not None:
        ch["name"] = req.name.strip() or ch["name"]
    if req.appearance is not None:
        ch["appearance"] = req.appearance.strip()
    persist_characters_on_anchors(v_anchors, characters)
    _save_job_cfg(job_dir, cfg)
    return _anchors_response(job_id, job_dir, cfg)


@router.delete("/{job_id}/anchors/characters/{char_id}", response_model=JobVisualAnchorsResponse)
def delete_character_anchor(job_id: str, char_id: str) -> JobVisualAnchorsResponse:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = [ch for ch in ensure_characters(v_anchors) if ch["id"] != char_id]
    img = character_image_path(job_dir, char_id)
    if img.is_file():
        img.unlink(missing_ok=True)
    persist_characters_on_anchors(v_anchors, characters)
    _save_job_cfg(job_dir, cfg)
    return _anchors_response(job_id, job_dir, cfg)


@router.post("/{job_id}/anchors/characters/{char_id}/hero", response_model=JobVisualAnchorsResponse)
def generate_character_hero(job_id: str, char_id: str) -> JobVisualAnchorsResponse:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    ch = _find_character(characters, char_id)
    try:
        _generate_one_character_sheet(job_dir, cfg, ch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini 定裝圖生成失敗: {str(e)}")
    persist_characters_on_anchors(v_anchors, characters)
    v_anchors["use_image_reference"] = True
    _save_job_cfg(job_dir, cfg)
    return _anchors_response(job_id, job_dir, cfg)


@router.post("/{job_id}/anchors/characters/{char_id}/hero/upload")
async def upload_character_hero(job_id: str, char_id: str, file: UploadFile = File(...)):
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    _find_character(characters, char_id)
    dest = character_image_path(job_dir, char_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())
    persist_characters_on_anchors(v_anchors, characters)
    v_anchors["use_image_reference"] = True
    _save_job_cfg(job_dir, cfg)
    return _anchors_response(job_id, job_dir, cfg)


@router.delete("/{job_id}/anchors/characters/{char_id}/hero", response_model=JobVisualAnchorsResponse)
def delete_character_hero(job_id: str, char_id: str) -> JobVisualAnchorsResponse:
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    img = character_image_path(job_dir, char_id)
    if img.is_file():
        img.unlink(missing_ok=True)
    return _anchors_response(job_id, job_dir)


@router.post("/{job_id}/anchors/sync-prompts")
def sync_job_prompts(job_id: str):
    """依據最新角色／環境錨點與專案生圖風格，重新批次產生全片分鏡英文出圖提示詞。"""
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    cfg = _load_job_cfg(job_dir)
    v_anchors = cfg.get("visual_anchors", {}) if isinstance(cfg.get("visual_anchors"), dict) else {}
    characters = ensure_characters(v_anchors)
    sub = v_anchors.get("subject", "") or compose_subject_anchor(characters)
    env = v_anchors.get("environment", "")

    updated_count = regenerate_job_scene_prompts(
        job_dir=job_dir,
        subject_anchor=sub,
        environment_anchor=env,
        characters=characters,
    )
    return {
        "success": True,
        "message": f"已依專案風格與最新視覺錨點同步更新全片 {updated_count} 場分鏡之英文提示詞",
        "updated_count": updated_count,
    }


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
        style_info = load_style_presets().get(req.style_id) or {}
        if style_info.get("prefix"):
            data["style_prefix"] = style_info["prefix"]
        if style_info.get("negative"):
            data["style_negative"] = style_info["negative"]

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


@router.post("/{job_id}/clear")
def clear_job_media(job_id: str):
    """
    全部清除/清空已生成素材：
    刪除所有分鏡的已生成圖片 (image.png, image.json, takes/)、語音 (speech.wav, speech.json, audio.wav)、
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
            for fname in ("image.png", "image.json", "speech.wav", "speech.json", "audio.wav", "pip.png"):
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
