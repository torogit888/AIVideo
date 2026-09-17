from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _format_srt_time(seconds: float) -> str:
    millis = int(round((seconds - int(seconds)) * 1000))
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(job_dir: Path) -> Path:
    scenes_dir = job_dir / "scenes"
    compose_dir = job_dir / "compose"
    compose_dir.mkdir(parents=True, exist_ok=True)
    srt_path = compose_dir / "timeline.srt"

    scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])
    current_time = 0.0
    srt_lines: list[str] = []
    index = 1

    for s_dir in scene_folders:
        scene_yaml_path = s_dir / "scene.yaml"
        if not scene_yaml_path.is_file():
            continue

        with open(scene_yaml_path, "r", encoding="utf-8") as f:
            scene_cfg = yaml.safe_load(f) or {}

        narration = str(scene_cfg.get("narration", "")).strip()
        # 移除 OmniVoice 語氣標籤，例如 [sigh], [laughter]
        import re
        clean_text = re.sub(r"\[[a-zA-Z0-9_\-]+\]", "", narration).strip()

        # 讀取時長
        duration = 5.0
        speech_json = s_dir / "speech.json"
        if speech_json.is_file():
            try:
                meta = json.loads(speech_json.read_text(encoding="utf-8"))
                duration = float(meta.get("duration_sec", 5.0))
            except Exception:
                pass

        start_str = _format_srt_time(current_time)
        end_time = current_time + duration
        end_str = _format_srt_time(end_time)

        srt_lines.append(f"{index}")
        srt_lines.append(f"{start_str} --> {end_str}")
        srt_lines.append(clean_text)
        srt_lines.append("")

        current_time = end_time
        index += 1

    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return srt_path


def run_srt(args: argparse.Namespace) -> int:
    job_dir = Path(args.job)
    if not job_dir.is_absolute():
        job_dir = REPO_ROOT / job_dir

    if not job_dir.is_dir():
        print(f"[fail] 找不到 Job 目錄：{job_dir}", file=sys.stderr)
        return 1

    srt_file = generate_srt(job_dir)
    print(f"[ok]   字幕已輸出：{srt_file.relative_to(REPO_ROOT)}")
    return 0
