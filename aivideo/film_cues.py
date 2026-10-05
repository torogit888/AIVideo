"""成片時間軸：每場起迄與 scene id。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def parse_scene_cues(job_dir: Path, default_duration: float = 5.5) -> list[dict]:
    scenes_dir = Path(job_dir) / "scenes"
    if not scenes_dir.is_dir():
        return []

    cues: list[dict] = []
    cursor = 0.0
    folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])
    for s_dir in folders:
        yaml_path = s_dir / "scene.yaml"
        title = s_dir.name
        scene_id = s_dir.name
        if yaml_path.is_file():
            cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            scene_id = str(cfg.get("id") or s_dir.name)
            title = str(cfg.get("title") or scene_id)

        duration = default_duration
        speech_json = s_dir / "speech.json"
        if speech_json.is_file():
            try:
                meta = json.loads(speech_json.read_text(encoding="utf-8"))
                duration = float(meta.get("duration_sec") or default_duration)
            except Exception:
                duration = default_duration

        start = cursor
        end = cursor + max(duration, 0.1)
        cues.append(
            {
                "scene_id": scene_id,
                "title": title,
                "start_sec": start,
                "end_sec": end,
            }
        )
        cursor = end
    return cues
