"""專案資料夾、鏡頭 id、主按鈕與媒體路徑。"""

from __future__ import annotations

import re
from datetime import datetime

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


def job_use_pip(cfg: dict | None) -> bool:
    if not isinstance(cfg, dict):
        return DEFAULT_USE_PIP
    return bool(cfg.get("use_pip", DEFAULT_USE_PIP))


def should_auto_pip(action: str, use_pip: bool = False) -> bool:
    """明確跑 pip，或 job 已打開考據開關且動作是 all。"""
    if action == "pip":
        return True
    if action == "all" and use_pip:
        return True
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
