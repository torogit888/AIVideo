from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

from aivideo.commands.srt import generate_srt

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_compose(args: argparse.Namespace) -> int:
    job_dir = Path(args.job)
    if not job_dir.is_absolute():
        job_dir = REPO_ROOT / job_dir

    if not job_dir.is_dir():
        print(f"[fail] 找不到 Job 目錄：{job_dir}", file=sys.stderr)
        return 1

    job_yaml_path = job_dir / "job.yaml"
    with open(job_yaml_path, "r", encoding="utf-8") as f:
        job_cfg = yaml.safe_load(f) or {}

    frame_cfg = job_cfg.get("frame", {})
    fps = int(frame_cfg.get("fps", 30))
    width = int(frame_cfg.get("deliver_width", 1920))
    height = int(frame_cfg.get("deliver_height", 1080))

    scenes_dir = job_dir / "scenes"
    compose_dir = job_dir / "compose"
    compose_dir.mkdir(parents=True, exist_ok=True)

    # 1. 產生或更新 SRT 與 ASS 字幕檔
    srt_path, ass_path = generate_srt(job_dir)
    print(f"[ok]   字幕檔已更新：{srt_path.name} 與 {ass_path.name}")

    scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])
    audio_files: list[Path] = []
    seg_videos: list[Path] = []

    print("[gen]  正在產生各場景 Ken Burns 鏡頭動畫...")
    for idx, s_dir in enumerate(scene_folders, 1):
        s_id = s_dir.name

        check_ctrl = getattr(args, "check_control", None)
        if check_ctrl and check_ctrl(phase="成片合成", s_dir=s_dir):
            print(f"[stop] 收到中止指令，停止成片合成")
            return 1

        img_path = s_dir / "image.png"
        wav_path = s_dir / "speech.wav"
        speech_json = s_dir / "speech.json"

        if not img_path.is_file():
            print(f"[fail] {s_id} 缺少 image.png，請先跑 aivideo images", file=sys.stderr)
            return 1
        if not wav_path.is_file():
            print(f"[fail] {s_id} 缺少 speech.wav，請先跑 aivideo tts", file=sys.stderr)
            return 1

        duration = 5.0
        if speech_json.is_file():
            try:
                meta = json.loads(speech_json.read_text(encoding="utf-8"))
                duration = float(meta.get("duration_sec", 5.0))
            except Exception:
                pass

        audio_files.append(wav_path)

        # 讀取該場景 scene.yaml 設定，檢查是否有啟用畫中畫 (Picture-in-Picture)
        scene_yaml_path = s_dir / "scene.yaml"
        scene_cfg = {}
        if scene_yaml_path.is_file():
            try:
                with open(scene_yaml_path, "r", encoding="utf-8") as yf:
                    scene_cfg = yaml.safe_load(yf) or {}
            except Exception:
                pass

        pip_cfg = scene_cfg.get("pip", {})
        pip_enabled = pip_cfg.get("enabled", True) if isinstance(pip_cfg, dict) else False
        pip_img_name = pip_cfg.get("image", "pip.png") if isinstance(pip_cfg, dict) else "pip.png"
        pip_path = s_dir / pip_img_name
        has_pip = pip_enabled and pip_path.is_file()

        # 產生單場推鏡影片
        seg_mp4 = compose_dir / f"seg_{idx:03d}.mp4"
        frames = max(1, int(round(duration * fps)))

        if has_pip:
            scale_ratio = float(pip_cfg.get("scale", 0.35))
            pip_w = int(round(width * scale_ratio))
            if pip_w % 2 != 0:
                pip_w += 1
            border_px = int(pip_cfg.get("border", 8))
            pos_key = str(pip_cfg.get("position", "top-right")).lower()

            pos_map = {
                "top-right": ("W-w-60", "60"),
                "top-left": ("60", "60"),
                "bottom-right": ("W-w-60", "H-h-140"),
                "bottom-left": ("60", "H-h-140"),
                "center": ("(W-w)/2", "(H-h)/2"),
            }
            pos_x, pos_y = pos_map.get(pos_key, ("W-w-60", "60"))

            fade_st = min(0.3, max(0.0, duration * 0.1))
            fade_d = min(0.4, max(0.1, duration * 0.2))

            filter_complex = (
                f"[0:v]scale=8000:-1,zoompan=z='min(zoom+0.0006,1.15)':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}[bg];"
                f"[1:v]scale={pip_w}:-1:force_original_aspect_ratio=decrease,"
                f"pad=w='iw+{border_px*2}':h='ih+{border_px*2}':x={border_px}:y={border_px}:color=white@0.9,"
                f"format=rgba,fade=t=in:st={fade_st:.2f}:d={fade_d:.2f}:alpha=1[pip_card];"
                f"[bg][pip_card]overlay=x='{pos_x}':y='{pos_y}':format=auto"
            )

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(img_path),
                "-loop", "1", "-i", str(pip_path),
                "-t", str(duration),
                "-filter_complex", filter_complex,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(seg_mp4),
            ]
        else:
            vf_filter = (
                f"scale=8000:-1,"
                f"zoompan=z='min(zoom+0.0006,1.15)':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
            )
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(img_path),
                "-t", str(duration),
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(seg_mp4),
            ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[fail] {s_id} 推鏡生成失敗：{proc.stderr}", file=sys.stderr)
            return 1

        seg_videos.append(seg_mp4)

    # 2. 合併音訊
    print("[gen]  正在合併各場景旁白音訊...")
    narration_wav = compose_dir / "narration.wav"
    audio_concat_txt = compose_dir / "audio_concat.txt"
    audio_concat_txt.write_text(
        "\n".join([f"file '{p.resolve().as_posix()}'" for p in audio_files]),
        encoding="utf-8",
    )
    cmd_audio = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(audio_concat_txt),
        "-c", "copy",
        str(narration_wav),
    ]
    proc = subprocess.run(cmd_audio, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[fail] 音訊串接失敗：{proc.stderr}", file=sys.stderr)
        return 1

    # 3. 串接視訊片段
    print("[gen]  正在串接視訊軌道...")
    video_concat_txt = compose_dir / "video_concat.txt"
    video_concat_txt.write_text(
        "\n".join([f"file '{p.resolve().as_posix()}'" for p in seg_videos]),
        encoding="utf-8",
    )
    raw_video_mp4 = compose_dir / "raw_video.mp4"
    cmd_video = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(video_concat_txt),
        "-c", "copy",
        str(raw_video_mp4),
    ]
    proc = subprocess.run(cmd_video, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[fail] 視訊串接失敗：{proc.stderr}", file=sys.stderr)
        return 1

    # 4. 最終合成：視訊 + 音訊 + ASS 字幕燒錄（1080p 絕對定位）
    print("[gen]  正在合流音訊、燒錄 1080p ASS 字幕並輸出影片...")
    final_film = compose_dir / "film.mp4"

    escaped_ass = str(ass_path.resolve().as_posix()).replace(":", r"\:")

    cmd_final = [
        "ffmpeg", "-y",
        "-i", str(raw_video_mp4),
        "-i", str(narration_wav),
        "-vf", f"subtitles='{escaped_ass}'",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(final_film),
    ]
    proc = subprocess.run(cmd_final, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[fail] 成片輸出失敗：{proc.stderr}", file=sys.stderr)
        return 1

    # 清理臨時中間檔
    audio_concat_txt.unlink(missing_ok=True)
    video_concat_txt.unlink(missing_ok=True)
    raw_video_mp4.unlink(missing_ok=True)
    for p in seg_videos:
        p.unlink(missing_ok=True)

    film_meta = {
        "output": str(final_film.relative_to(REPO_ROOT)),
        "resolution": f"{width}x{height}",
        "fps": fps,
        "scenes_count": len(scene_folders),
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
    }
    (compose_dir / "film.json").write_text(json.dumps(film_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[ok]   成片合成大功告成！\n       檔案路徑：{final_film.relative_to(REPO_ROOT)}")
    return 0
