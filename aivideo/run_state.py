"""管線狀態落盤 jobs/<id>/run.json，reload 仍看得到上一輪進度。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_json_path(job_dir: Path) -> Path:
    return job_dir / "run.json"


def snapshot_runner(runner: Any) -> dict[str, Any]:
    live_dir = getattr(runner, "live_dir", None)
    scene_id = live_dir.name if live_dir is not None else None
    has_image = False
    has_audio = False
    if live_dir is not None:
        try:
            has_image = (live_dir / "image.png").is_file()
            has_audio = (live_dir / "speech.wav").is_file() or (live_dir / "audio.wav").is_file()
        except OSError:
            pass
    return {
        "job_id": getattr(runner, "job_name", ""),
        "is_running": bool(getattr(runner, "is_running", False)),
        "is_paused": bool(getattr(runner, "is_paused", False)),
        "is_done": bool(getattr(runner, "is_done", False)),
        "is_stopped": bool(getattr(runner, "is_stopped", False)),
        "mode": getattr(runner, "mode", "") or "",
        "phase": getattr(runner, "live_phase", "") or "",
        "progress": float(getattr(runner, "progress", 0.0) or 0.0),
        "message": getattr(runner, "status_msg", "") or "",
        "error": getattr(runner, "error_msg", None),
        "scene_id": scene_id,
        "has_image": has_image,
        "has_audio": has_audio,
        "cooldown_remaining": int(getattr(runner, "cooldown_remaining", 0) or 0),
        "cooldown_total": int(getattr(runner, "cooldown_total", 0) or 0),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_run_json(job_dir: Path, data: dict[str, Any]) -> None:
    path = run_json_path(job_dir)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# 模組級快取：記錄各 job 上次實際寫入磁碟的實質內容，避免內容未變時重複寫盤
_LAST_SAVED_STATE: dict[str, dict[str, Any]] = {}


def persist_runner(runner: Any) -> dict[str, Any]:
    data = snapshot_runner(runner)
    job_path = getattr(runner, "job_path", None)
    if job_path is not None:
        try:
            job_key = str(job_path)
            # 提取排除 updated_at 之後的純實質內容
            essential_fields = {k: v for k, v in data.items() if k != "updated_at"}
            last_saved = _LAST_SAVED_STATE.get(job_key)

            # 實質內容完全無變更時直接跳過，絕不無謂刷寫磁碟
            if last_saved == essential_fields:
                return data

            write_run_json(Path(job_path), data)
            _LAST_SAVED_STATE[job_key] = essential_fields
        except OSError:
            pass
    return data


def load_run_json(job_dir: Path) -> dict[str, Any] | None:
    path = run_json_path(job_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None
