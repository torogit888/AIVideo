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


def persist_runner(runner: Any) -> dict[str, Any]:
    data = snapshot_runner(runner)
    job_path = getattr(runner, "job_path", None)
    if job_path is not None:
        try:
            write_run_json(Path(job_path), data)
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
