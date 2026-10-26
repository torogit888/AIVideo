"""專案資料夾、鏡頭 id、主按鈕與媒體路徑。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import yaml

from aivideo.spoken import strip_omnivoice_tags

DEFAULT_VOICE_ID = "tw_female01"

_GENERIC_TITLE_RE = re.compile(r"^第\s*\d+\s*幕$")


def ascii_slug(text: str, fallback: str = "story") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\s_-]", "", text or "").strip()
    slug = re.sub(r"[-\s]+", "_", cleaned).strip("_")[:30]
    return slug or fallback


def build_job_id(topic: str, slug: str | None = None, today: str | None = None) -> str:
    date_part = today or datetime.now().strftime("%Y%m%d")
    custom = (slug or "").strip()
    part = ascii_slug(custom) if custom else ascii_slug(topic)
    return f"{date_part}_{part}"


def resolve_unique_job_id(jobs_dir: Path, base_job_id: str) -> str:
    """若同日同名資料夾已存在，自動加上 _2、_3 等序號，避免靜默覆蓋舊專案素材。"""
    candidate = base_job_id
    seq = 2
    while (jobs_dir / candidate).exists():
        candidate = f"{base_job_id}_{seq}"
        seq += 1
    return candidate


def scene_folder_id(index: int) -> str:
    return f"{index:03d}_shot_{index}"


def scene_title_from_narration(narration: str, max_chars: int = 16) -> str:
    text = strip_omnivoice_tags(narration or "")
    text = re.sub(r"\s+", "", text)
    for sep in ("，", "。", "！", "？", "、", "；", ",", ".", "!", "?"):
        if sep in text:
            text = text.split(sep, 1)[0]
            break
    text = text[:max_chars]
    if not text or _GENERIC_TITLE_RE.fullmatch(text):
        return "鏡頭"
    return text


def srt_media_url(job_id: str) -> str:
    return f"/media/jobs/{job_id}/compose/timeline.srt"


STORYBOARD_GHOST_ACTIONS = ("images", "tts", "compose")
STORYBOARD_OVERFLOW_ACTIONS = (
    "continuity",
    "pip",
    "clear_images",
    "clear_audio",
    "clear_all",
    "force",
)
CONNECTION_LIGHTS = ("gemini", "comfy")
DEFAULT_USE_PIP = True
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"
SPOTLIGHT_MODES = ("spotlight", "focus", "black_bg", "fullscreen", "broll")


def job_use_pip(cfg: dict | None) -> bool:
    if not isinstance(cfg, dict):
        return DEFAULT_USE_PIP
    if "use_pip" not in cfg or cfg["use_pip"] is None:
        return DEFAULT_USE_PIP
    return bool(cfg.get("use_pip"))


def should_auto_pip(action: str, use_pip: bool = DEFAULT_USE_PIP) -> bool:
    """若一鍵全流程開啟且 use_pip 為 True，或明確跑 pip 批次，則啟用自動考據。"""
    if action == "pip":
        return True
    if action == "all" and use_pip:
        return True
    return False


def is_scene_visual_ready(scene_dir: Path) -> bool:
    """全站統一判斷該鏡頭是否已有可用主畫面（AI 圖、考據影片、或黑底聚焦考據圖）。"""
    if (scene_dir / "image.png").is_file() or (scene_dir / "pip.mp4").is_file():
        return True
    pip_file = scene_dir / "pip.png"
    s_yaml = scene_dir / "scene.yaml"
    if pip_file.is_file() and s_yaml.is_file():
        try:
            sc_data = yaml.safe_load(s_yaml.read_text(encoding="utf-8")) or {}
            p_mode = str((sc_data.get("pip") or {}).get("mode", "")).lower()
            if p_mode in SPOTLIGHT_MODES:
                return True
        except Exception:
            pass
    return False


def is_film_stale(job_dir: Path) -> bool:
    """判斷 compose/film.mp4 是否早於腳本或任一分鏡的口白、畫面、語音修改時間。"""
    film_file = job_dir / "compose" / "film.mp4"
    if not film_file.is_file():
        return False
    try:
        film_mtime = film_file.stat().st_mtime
    except OSError:
        return False

    candidates: list[Path] = [job_dir / "script.md"]
    scenes_dir = job_dir / "scenes"
    if scenes_dir.is_dir():
        for s_dir in scenes_dir.iterdir():
            if not s_dir.is_dir():
                continue
            for fname in ("scene.yaml", "image.png", "pip.png", "pip.mp4", "speech.wav"):
                candidates.append(s_dir / fname)

    for p in candidates:
        try:
            if p.is_file() and p.stat().st_mtime > film_mtime + 1e-3:
                return True
        except OSError:
            continue
    return False


def script_workspace_mode(job_id: str | None) -> str:
    return "edit" if job_id else "new"


def should_prompt_recut(script_changed: bool, has_scenes: bool) -> bool:
    return bool(script_changed and has_scenes)


def primary_pipeline_action(
    images_ready: int,
    audio_ready: int,
    total: int,
    has_film: bool,
) -> dict[str, str | None]:
    if total <= 0:
        return {"label": "生成腳本", "action": None}
    if images_ready < total:
        return {"label": "生成未完成畫面", "action": "images"}
    if audio_ready < total:
        return {"label": "生成配音", "action": "tts"}
    if not has_film:
        return {"label": "合成 1080p", "action": "compose"}
    return {"label": "預覽成片", "action": "preview"}
