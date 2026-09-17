from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _format_srt_time(seconds: float) -> str:
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_ass_time(seconds: float) -> str:
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def wrap_subtitle_text(text: str, max_chars: int = 18) -> list[str]:
    """智慧折行中文字幕，嚴格限制最多 2 行，遵守避頭尾法則與自然語意斷句。"""
    clean = text.strip()
    if len(clean) <= max_chars:
        return [clean]

    # 尋找靠近文字中央的自然語意斷點（優先在逗號、頓號、空格、破折號，絕不用冒號或開引號）
    split_chars = ["，", "、", " ", "—", "；"]
    mid = len(clean) // 2
    best_pos = -1
    min_dist = len(clean)

    for idx, ch in enumerate(clean):
        if ch in split_chars:
            if 5 <= idx <= len(clean) - 5:
                # 避頭尾：若下一個字是開引號（如 ：「 或 ，「），絕不斷在此處
                if idx + 1 < len(clean) and clean[idx + 1] in ["「", "『", "“", "（", "\"", "'"]:
                    continue
                dist = abs(idx - mid)
                if dist < min_dist:
                    min_dist = dist
                    best_pos = idx

    if best_pos != -1:
        line1 = clean[:best_pos + 1].strip()
        line2 = clean[best_pos + 1:].strip()
    else:
        # 若無合適標點，從中點切分
        line1 = clean[:mid].strip()
        line2 = clean[mid:].strip()

    # 避頭尾法則：下一行開頭禁止為閉引號或標點符號
    invalid_start = ["，", "、", "。", "！", "？", "：", "；", "」", "』", "）", "”", "’"]
    while line2 and line2[0] in invalid_start:
        line1 += line2[0]
        line2 = line2[1:].strip()

    if not line2:
        return [line1]

    # 嚴格保證最多 2 行
    return [line1, line2]


def generate_srt(job_dir: Path) -> tuple[Path, Path]:
    scenes_dir = job_dir / "scenes"
    compose_dir = job_dir / "compose"
    compose_dir.mkdir(parents=True, exist_ok=True)
    srt_path = compose_dir / "timeline.srt"
    ass_path = compose_dir / "timeline.ass"

    scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])
    current_time = 0.0
    srt_lines: list[str] = []
    ass_events: list[str] = []
    index = 1

    for s_dir in scene_folders:
        scene_yaml_path = s_dir / "scene.yaml"
        if not scene_yaml_path.is_file():
            continue

        with open(scene_yaml_path, "r", encoding="utf-8") as f:
            scene_cfg = yaml.safe_load(f) or {}

        narration = str(scene_cfg.get("narration", "")).strip()
        import re

        speech_json = s_dir / "speech.json"
        meta = {}
        if speech_json.is_file():
            try:
                meta = json.loads(speech_json.read_text(encoding="utf-8"))
            except Exception:
                pass

        duration = float(meta.get("duration_sec", 5.0))
        sentences_meta = meta.get("sentences", [])

        if sentences_meta and isinstance(sentences_meta, list):
            for s_info in sentences_meta:
                s_text = str(s_info.get("text", "")).strip()
                clean_s = re.sub(r"\[[a-zA-Z0-9_\-]+\]", "", s_text).strip()
                if not clean_s:
                    continue
                s_start = current_time + float(s_info.get("start_sec", 0.0))
                s_end = current_time + float(s_info.get("end_sec", s_start + 1.0))

                wrapped_lines = wrap_subtitle_text(clean_s, max_chars=18)
                srt_content = "\n".join(wrapped_lines)
                ass_content = r"\N".join(wrapped_lines)

                srt_lines.append(f"{index}")
                srt_lines.append(f"{_format_srt_time(s_start)} --> {_format_srt_time(s_end)}")
                srt_lines.append(srt_content)
                srt_lines.append("")

                ass_events.append(
                    f"Dialogue: 0,{_format_ass_time(s_start)},{_format_ass_time(s_end)},Default,,0,0,0,,{ass_content}"
                )
                index += 1
            current_time += duration
        else:
            clean_text = re.sub(r"\[[a-zA-Z0-9_\-]+\]", "", narration).strip()
            start_str = _format_srt_time(current_time)
            end_time = current_time + duration
            end_str = _format_srt_time(end_time)

            wrapped_lines = wrap_subtitle_text(clean_text, max_chars=18)
            srt_content = "\n".join(wrapped_lines)
            ass_content = r"\N".join(wrapped_lines)

            srt_lines.append(f"{index}")
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(srt_content)
            srt_lines.append("")

            ass_events.append(
                f"Dialogue: 0,{_format_ass_time(current_time)},{_format_ass_time(end_time)},Default,,0,0,0,,{ass_content}"
            )

            current_time = end_time
            index += 1

    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    # 輸出 1920x1080 專用 ASS 字幕檔
    ass_template = f"""[Script Info]
Title: AIVideo Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK TC,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3.2,1.5,2,100,100,65,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
{"\n".join(ass_events)}
"""
    ass_path.write_text(ass_template, encoding="utf-8")
    return srt_path, ass_path


def run_srt(args: argparse.Namespace) -> int:
    job_dir = Path(args.job)
    if not job_dir.is_absolute():
        job_dir = REPO_ROOT / job_dir

    if not job_dir.is_dir():
        print(f"[fail] 找不到 Job 目錄：{job_dir}", file=sys.stderr)
        return 1

    srt_file, ass_file = generate_srt(job_dir)
    print(f"[ok]   字幕已輸出：{srt_file.relative_to(REPO_ROOT)} 與 {ass_file.relative_to(REPO_ROOT)}")
    return 0
