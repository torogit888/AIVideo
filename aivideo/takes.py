"""分鏡 takes/ 清單與設為 current。只讀檔名與既有 current 欄位。"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

IMAGE_TAKE_RE = re.compile(r"^image_\d{8}T\d{6}$")
SPEECH_TAKE_RE = re.compile(r"^speech_\d{8}T\d{6}$")
AUX_SPEECH_RE = re.compile(r"_(sent_|silence|concat)")


def is_image_take_id(take_id: str) -> bool:
    return bool(IMAGE_TAKE_RE.fullmatch(take_id or ""))


def is_speech_take_id(take_id: str) -> bool:
    return bool(SPEECH_TAKE_RE.fullmatch(take_id or ""))


def _mtime_iso(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def _read_created_at(meta_path: Path, media_path: Path) -> str | None:
    if meta_path.is_file():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            created = data.get("created_at")
            if created:
                return str(created)
        except Exception:
            pass
    return _mtime_iso(media_path)


def _current_ids(scene_dir: Path) -> dict[str, str | None]:
    yaml_path = scene_dir / "scene.yaml"
    current: dict[str, Any] = {}
    if yaml_path.is_file():
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            current = data.get("current") or {}
        except Exception:
            current = {}
    return {
        "image_take": current.get("image_take") or None,
        "speech_take": current.get("speech_take") or None,
    }


def _media_url(job_id: str, scene_id: str, rel: str, mtime: int) -> str:
    job_q = quote(job_id)
    scene_q = quote(scene_id)
    return f"/media/jobs/{job_q}/scenes/{scene_q}/{rel}?t={mtime}"


def list_scene_takes(scene_dir: Path, job_id: str = "", scene_id: str = "") -> dict[str, list[dict[str, Any]]]:
    """由 takes/ 檔名列出圖／聲歷史。略過句段 wav 與靜音檔。"""
    takes_dir = scene_dir / "takes"
    scene_id = scene_id or scene_dir.name
    job_id = job_id or scene_dir.parent.parent.name
    current = _current_ids(scene_dir)

    images: list[dict[str, Any]] = []
    speeches: list[dict[str, Any]] = []

    if not takes_dir.is_dir():
        return {"images": images, "speeches": speeches}

    for png in sorted(takes_dir.glob("*.png")):
        take_id = png.stem
        if not is_image_take_id(take_id):
            continue
        mtime = int(png.stat().st_mtime)
        images.append(
            {
                "take_id": take_id,
                "kind": "image",
                "filename": png.name,
                "url": _media_url(job_id, scene_id, f"takes/{png.name}", mtime),
                "created_at": _read_created_at(png.with_suffix(".json"), png),
                "is_current": current.get("image_take") == take_id,
            }
        )

    for wav in sorted(takes_dir.glob("*.wav")):
        take_id = wav.stem
        if AUX_SPEECH_RE.search(take_id):
            continue
        if not is_speech_take_id(take_id):
            continue
        mtime = int(wav.stat().st_mtime)
        speeches.append(
            {
                "take_id": take_id,
                "kind": "speech",
                "filename": wav.name,
                "url": _media_url(job_id, scene_id, f"takes/{wav.name}", mtime),
                "created_at": _read_created_at(wav.with_suffix(".json"), wav),
                "is_current": current.get("speech_take") == take_id,
            }
        )

    images.sort(key=lambda t: t.get("created_at") or t["take_id"], reverse=True)
    speeches.sort(key=lambda t: t.get("created_at") or t["take_id"], reverse=True)
    return {"images": images, "speeches": speeches}


def select_current_take(scene_dir: Path, take_id: str, kind: str) -> dict[str, Any]:
    """把指定 take 複製成 current（image.png / speech.wav），並寫入 scene.yaml。"""
    kind = (kind or "").strip().lower()
    if kind in ("image", "img"):
        kind = "image"
    elif kind in ("speech", "audio", "tts"):
        kind = "speech"
    else:
        raise ValueError("kind 必須是 image 或 speech")

    takes_dir = scene_dir / "takes"
    if kind == "image":
        if not is_image_take_id(take_id):
            raise FileNotFoundError(f"不是有效的畫面 take id: {take_id}")
        src = takes_dir / f"{take_id}.png"
        if not src.is_file():
            raise FileNotFoundError(f"找不到畫面 take: {take_id}")
        shutil.copy2(src, scene_dir / "image.png")
        src_json = takes_dir / f"{take_id}.json"
        if src_json.is_file():
            shutil.copy2(src_json, scene_dir / "image.json")
        current_key = "image_take"
    else:
        if not is_speech_take_id(take_id):
            raise FileNotFoundError(f"不是有效的配音 take id: {take_id}")
        src = takes_dir / f"{take_id}.wav"
        if not src.is_file():
            raise FileNotFoundError(f"找不到配音 take: {take_id}")
        shutil.copy2(src, scene_dir / "speech.wav")
        src_json = takes_dir / f"{take_id}.json"
        if src_json.is_file():
            shutil.copy2(src_json, scene_dir / "speech.json")
        current_key = "speech_take"

    yaml_path = scene_dir / "scene.yaml"
    data: dict[str, Any] = {}
    if yaml_path.is_file():
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    current = data.get("current") if isinstance(data.get("current"), dict) else {}
    current[current_key] = take_id
    data["current"] = current
    yaml_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return {"take_id": take_id, "kind": kind, "current": current}


def gc_scene_takes(scene_dir: Path, keep: int = 3) -> dict[str, Any]:
    """刪除過舊 takes，保留 current 與最新 keep 個。句段／靜音檔一併清。"""
    keep = max(1, int(keep))
    takes_dir = scene_dir / "takes"
    listed = list_scene_takes(scene_dir)
    current = _current_ids(scene_dir)
    removed: list[str] = []
    kept: list[str] = []

    def _gc_kind(items: list[dict[str, Any]], current_id: str | None) -> None:
        keep_ids = {t["take_id"] for t in items[:keep]}
        if current_id:
            keep_ids.add(current_id)
        for t in items:
            tid = t["take_id"]
            if tid in keep_ids:
                kept.append(tid)
                continue
            for suffix in (".png", ".wav", ".json"):
                p = takes_dir / f"{tid}{suffix}"
                if p.is_file():
                    p.unlink()
                    removed.append(p.name)

    if takes_dir.is_dir():
        _gc_kind(listed["images"], current.get("image_take"))
        _gc_kind(listed["speeches"], current.get("speech_take"))
        for wav in list(takes_dir.glob("*.wav")):
            if AUX_SPEECH_RE.search(wav.stem):
                wav.unlink()
                removed.append(wav.name)
                json_side = wav.with_suffix(".json")
                if json_side.is_file():
                    json_side.unlink()
                    removed.append(json_side.name)

    return {
        "removed": len(removed),
        "removed_names": removed,
        "kept": kept,
        "keep": keep,
    }


def gc_job_takes(job_dir: Path, keep: int = 3, scene: str | None = None) -> dict[str, Any]:
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return {"scenes": 0, "removed": 0, "keep": keep}
    total_removed = 0
    n = 0
    for s_dir in sorted(scenes_dir.iterdir()):
        if not s_dir.is_dir():
            continue
        if scene and not (
            s_dir.name == scene or s_dir.name.startswith(f"{scene}_") or s_dir.name.startswith(scene)
        ):
            continue
        n += 1
        total_removed += int(gc_scene_takes(s_dir, keep=keep)["removed"])
    return {"scenes": n, "removed": total_removed, "keep": keep}
