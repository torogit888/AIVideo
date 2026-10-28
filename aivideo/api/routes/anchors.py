"""專案視覺一致性與角色定裝路由（由 jobs.py 拆出，掛載於 /jobs 下）。"""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile

from aivideo.api.schemas import (
    AddCharacterRequest,
    AnalyzeAnchorsRequest,
    AnalyzeAnchorsResponse,
    CharacterAnchor,
    CharacterAnchorDraft,
    GenerateHeroAnchorResponse,
    JobVisualAnchorsResponse,
    PatchCharacterRequest,
    UpdateVisualAnchorsRequest,
)
from aivideo.gemini_image import generate_image
from aivideo.story_generator import (
    DEFAULT_STYLE_PRESETS,
    extract_story_visual_anchors,
    load_style_presets,
    regenerate_job_scene_prompts,
)
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
)

router = APIRouter(prefix="/jobs", tags=["專案視覺定裝"])
REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_DIR = REPO_ROOT / "jobs"


def _jobs_dir() -> Path:
    from aivideo.api.routes import jobs as jobs_route

    return getattr(jobs_route, "JOBS_DIR", JOBS_DIR)


def _load_job_cfg(job_dir: Path) -> dict:
    from aivideo.job_files import load_job_config

    path = job_dir / "job.yaml"
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


def _find_character(characters: list[dict[str, str]], char_id: str) -> dict[str, str]:
    for ch in characters:
        if ch["id"] == char_id:
            return ch
    raise HTTPException(status_code=404, detail="找不到此角色")


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
            CharacterAnchorDraft(
                id=ch["id"],
                name=ch["name"],
                appearance=ch.get("appearance", ""),
                entity_type=ch.get("entity_type", "character"),
            )
            for ch in characters
        ],
    )


@router.get("/{job_id}/anchors", response_model=JobVisualAnchorsResponse)
def get_job_anchors(job_id: str) -> JobVisualAnchorsResponse:
    """取得特定專案的視覺一致性錨點設定與定裝基準圖狀態。"""
    job_dir = _jobs_dir() / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    return _anchors_response(job_id, job_dir)


@router.patch("/{job_id}/anchors", response_model=JobVisualAnchorsResponse)
def update_job_anchors(job_id: str, req: UpdateVisualAnchorsRequest) -> JobVisualAnchorsResponse:
    """更新專案的角色外觀錨點、環境光影錨點或切換定裝圖多模態參考開關。"""
    job_dir = _jobs_dir() / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)

    if req.environment is not None:
        v_anchors["environment"] = req.environment.strip()
    if req.use_image_reference is not None:
        v_anchors["use_image_reference"] = req.use_image_reference
    if req.characters is not None:
        old_chars = ensure_characters(v_anchors)
        characters = normalize_characters(
            [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in req.characters]
        )
        persist_characters_on_anchors(v_anchors, characters)
        if req.clear_hero_images:
            clear_all_character_images(job_dir)
        else:
            invalidate_changed_character_images(job_dir, old_chars, characters)
    elif req.subject is not None:
        old_chars = ensure_characters(v_anchors)
        v_anchors["subject"] = req.subject.strip()
        if not v_anchors.get("characters"):
            new_chars = normalize_characters(
                [{"id": "main", "name": "Main Subject", "appearance": req.subject.strip()}]
            )
            persist_characters_on_anchors(v_anchors, new_chars)
            if req.clear_hero_images:
                clear_all_character_images(job_dir)
            else:
                invalidate_changed_character_images(job_dir, old_chars, new_chars)
    elif req.clear_hero_images:
        clear_all_character_images(job_dir)

    _save_job_cfg(job_dir, cfg)
    return _anchors_response(job_id, job_dir, cfg)


@router.post("/{job_id}/anchors/hero", response_model=GenerateHeroAnchorResponse)
def generate_hero_anchor(job_id: str) -> GenerateHeroAnchorResponse:
    """依專案生圖風格，為每位角色各生成一張 16:9 定裝圖。"""
    job_dir = _jobs_dir() / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")

    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    if not characters:
        raise HTTPException(status_code=400, detail="尚未設定任何角色外觀錨點，請先分析腳本或手動新增角色")

    legacy_hero = legacy_hero_path(job_dir)
    if legacy_hero.is_file():
        legacy_hero.unlink(missing_ok=True)

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
    job_dir = _jobs_dir() / job_id
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
    job_dir = _jobs_dir() / job_id
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
    job_dir = _jobs_dir() / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    extra = normalize_characters(
        [{"name": req.name, "appearance": req.appearance, "entity_type": req.entity_type}]
    )
    if not extra:
        raise HTTPException(status_code=400, detail="角色名稱不能為空")
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
    job_dir = _jobs_dir() / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    cfg = _load_job_cfg(job_dir)
    v_anchors = _ensure_visual_anchors(cfg)
    characters = ensure_characters(v_anchors)
    ch = _find_character(characters, char_id)
    old_name = ch.get("name", "")
    old_app = ch.get("appearance", "")
    old_type = ch.get("entity_type", "character")
    if req.name is not None:
        ch["name"] = req.name.strip() or ch["name"]
    if req.appearance is not None:
        ch["appearance"] = req.appearance.strip()
    if req.entity_type is not None:
        ch["entity_type"] = req.entity_type.strip().lower()
    if ch.get("name", "") != old_name or ch.get("appearance", "") != old_app or ch.get("entity_type", "character") != old_type:
        img = character_image_path(job_dir, char_id)
        if img.is_file():
            img.unlink(missing_ok=True)
        legacy_hero = legacy_hero_path(job_dir)
        if legacy_hero.is_file():
            legacy_hero.unlink(missing_ok=True)
    persist_characters_on_anchors(v_anchors, characters)
    _save_job_cfg(job_dir, cfg)
    return _anchors_response(job_id, job_dir, cfg)


@router.delete("/{job_id}/anchors/characters/{char_id}", response_model=JobVisualAnchorsResponse)
def delete_character_anchor(job_id: str, char_id: str) -> JobVisualAnchorsResponse:
    job_dir = _jobs_dir() / job_id
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
    job_dir = _jobs_dir() / job_id
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
    job_dir = _jobs_dir() / job_id
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
    job_dir = _jobs_dir() / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="專案不存在")
    img = character_image_path(job_dir, char_id)
    if img.is_file():
        img.unlink(missing_ok=True)
    return _anchors_response(job_id, job_dir)


@router.post("/{job_id}/anchors/sync-prompts")
def sync_job_prompts(job_id: str):
    """依據最新角色／環境錨點與專案生圖風格，重新批次產生全片分鏡英文出圖提示詞。"""
    job_dir = _jobs_dir() / job_id
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
