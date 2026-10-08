from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import yaml

from aivideo.commands.srt import generate_srt

REPO_ROOT = Path(__file__).resolve().parents[2]


def _render_single_segment(
    idx: int,
    s_dir: Path,
    compose_dir: Path,
    width: int,
    height: int,
    fps: int,
) -> tuple[int, Path, Path, float]:
    """渲染單場推鏡與 PiP 影片片段，回傳 (idx, seg_mp4, wav_path, duration)"""
    s_id = s_dir.name
    img_path = s_dir / "image.png"
    wav_path = s_dir / "speech.wav"
    speech_json = s_dir / "speech.json"

    duration = 5.0
    if speech_json.is_file():
        try:
            meta = json.loads(speech_json.read_text(encoding="utf-8"))
            duration = float(meta.get("duration_sec", 5.0))
        except Exception:
            pass

    # 讀取該場景 scene.yaml 設定，檢查是否有啟用畫中畫 (Picture-in-Picture) 或黑底考據圖 (Spotlight)
    scene_yaml_path = s_dir / "scene.yaml"
    scene_cfg = {}
    if scene_yaml_path.is_file():
        try:
            with open(scene_yaml_path, "r", encoding="utf-8") as yf:
                scene_cfg = yaml.safe_load(yf) or {}
        except Exception:
            pass

    pip_cfg = scene_cfg.get("pip", {})
    pip_enabled = bool(pip_cfg.get("enabled", False)) if isinstance(pip_cfg, dict) else False
    pip_img_name = (pip_cfg.get("image") or "pip.png") if isinstance(pip_cfg, dict) else "pip.png"
    pip_path = s_dir / pip_img_name
    has_pip = pip_enabled and pip_path.is_file()

    pip_mode = str(pip_cfg.get("mode") or "pip").lower() if has_pip else ""
    is_spotlight = has_pip and pip_mode in ("spotlight", "focus", "black_bg", "fullscreen")

    # 若為黑底歷史聚焦 (spotlight) 且已有考據真實照片，則畫面以此為主角，不強制要求 image.png
    if not is_spotlight and not img_path.is_file():
        raise FileNotFoundError(f"{s_id} 缺少 image.png，請先跑 aivideo images")
    if not wav_path.is_file():
        raise FileNotFoundError(f"{s_id} 缺少 speech.wav，請先跑 aivideo tts")

    seg_mp4 = compose_dir / f"seg_{idx:03d}.mp4"
    frames = max(1, int(round(duration * fps)))

    if has_pip:
        pip_mode = str(pip_cfg.get("mode", "pip")).lower()

        # ----------------------------------------------------
        # 模式 B: 黑底歷史原照聚焦 (Archival Spotlight + 8000px 座標級抗抖動緩慢推鏡)
        # ----------------------------------------------------
        if pip_mode in ("spotlight", "focus", "black_bg", "fullscreen"):
            cw = width * 4
            ch = height * 4
            spot_w = int(round(cw * float(pip_cfg.get("scale", 0.60))))
            if spot_w % 2 != 0:
                spot_w += 1
            border_px = int(pip_cfg.get("border", 16))

            filter_complex = (
                f"color=c=black:s={cw}x{ch}:r={fps}:d={duration}[cbg];"
                f"[0:v]format=rgba,scale={spot_w}:-1:force_original_aspect_ratio=decrease[photo_s];"
                f"[photo_s]split=2[fg][bg_src];"
                f"[bg_src]drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:replace=1[white_bg];"
                f"[white_bg][fg]overlay=0:0,"
                f"pad=w='trunc((iw+{border_px*2})/2)*2':h='trunc((ih+{border_px*2})/2)*2':x={border_px}:y={border_px}:color=white[photo];"
                f"[cbg][photo]overlay=x='(W-w)/2':y='(H-h)/2-80':shortest=1[comp];"
                f"[comp]zoompan=z='min(zoom+0.0004,1.08)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps},"
                f"fade=t=in:st=0.0:d=0.6:alpha=1[v]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(pip_path),
                "-t", str(duration),
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                str(seg_mp4),
            ]
        else:
            # ----------------------------------------------------
            # 模式 A: 畫中畫小卡 (PiP) 疊加 + 4*iw 超採樣背景推鏡
            # ----------------------------------------------------
            scale_ratio = float(pip_cfg.get("scale", 0.24))
            pip_w = int(round(width * scale_ratio))
            if pip_w % 2 != 0:
                pip_w += 1
            border_px = int(pip_cfg.get("border", 5))
            pos_key = str(pip_cfg.get("position", "right-center")).lower()

            pos_map = {
                "right-center": ("W-w-60", "(H-h)/2"),
                "top-right": ("W-w-60", "60"),
                "top-left": ("60", "60"),
                "bottom-right": ("W-w-60", "H-h-140"),
                "bottom-left": ("60", "H-h-140"),
                "center": ("(W-w)/2", "(H-h)/2"),
            }
            pos_x, pos_y = pos_map.get(pos_key, ("W-w-60", "(H-h)/2"))

            # 畫中畫 (PiP) 出現時機：在該幕中後半部（約 45%~48% 處）才淡入，留給觀眾沉浸前奏，不再一開場 0.3 秒就彈出遮擋
            fade_d = 0.5
            if duration <= 3.0:
                fade_st = max(0.6, duration * 0.40)
            else:
                fade_st = min(duration * 0.48, max(1.5, duration - 1.5))

            filter_complex = (
                f"[0:v]scale=4*iw:-1:flags=bicubic,"
                f"zoompan=z='min(zoom+0.0006,1.15)':d={frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}[bg];"
                f"[1:v]format=rgba,scale={pip_w}:-1:force_original_aspect_ratio=decrease[pip_s];"
                f"[pip_s]split=2[fg][bg_src];"
                f"[bg_src]drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:replace=1[white_bg];"
                f"[white_bg][fg]overlay=0:0,"
                f"pad=w='trunc((iw+{border_px*2})/2)*2':h='trunc((ih+{border_px*2})/2)*2':x={border_px}:y={border_px}:color=white,"
                f"fade=t=in:st={fade_st:.2f}:d={fade_d:.2f}:alpha=1[pip_card];"
                f"[bg][pip_card]overlay=x='{pos_x}':y='{pos_y}':format=auto:shortest=1[v]"
            )

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(img_path),
                "-loop", "1", "-i", str(pip_path),
                "-t", str(duration),
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                str(seg_mp4),
            ]
    else:
        # 4*iw (約 7680px) 超採樣網格運算，徹底消除整數座標跳格抖動 (Sub-pixel Jitter)
        vf_filter = (
            f"scale=4*iw:-1:flags=bicubic,"
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
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(seg_mp4),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{s_id} 推鏡生成失敗：{proc.stderr}")

    return idx, seg_mp4, wav_path, duration


def run_compose(args: argparse.Namespace, progress_callback: Any = None) -> int:
    job_dir = Path(args.job)
    if not job_dir.is_absolute():
        job_dir = REPO_ROOT / job_dir

    if not job_dir.is_dir():
        print(f"[fail] 找不到 Job 目錄：{job_dir}", file=sys.stderr)
        return 1

    cb = progress_callback or getattr(args, "progress_callback", None)

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
    if not scene_folders:
        print(f"[fail] {scenes_dir} 內無任何分鏡場景資料夾", file=sys.stderr)
        return 1

    # 判斷是否燒錄字幕至畫面 (預設不加字幕，依使用者需求)
    arg_burn = getattr(args, "burn_subtitles", None)
    if arg_burn is not None:
        burn_subtitles = bool(arg_burn)
    else:
        sub_mode = str(job_cfg.get("subtitle", {}).get("mode", "none")).strip().lower()
        burn_subtitles = (sub_mode == "hard")

    workers = min(4, os.cpu_count() or 4)
    print(f"[gen]  正在以 {workers} 線程平行產生各場景鏡頭動畫 (預設檔: ultrafast)...")

    results: list[tuple[int, Path, Path, float]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_render_single_segment, idx, s_dir, compose_dir, width, height, fps): (idx, s_dir)
            for idx, s_dir in enumerate(scene_folders, 1)
        }
        for future in as_completed(future_map):
            idx, s_dir = future_map[future]
            check_ctrl = getattr(args, "check_control", None)
            if check_ctrl and check_ctrl(phase="成片合成", s_dir=s_dir):
                print(f"[stop] 收到中止指令，停止成片合成")
                executor.shutdown(wait=False, cancel_futures=True)
                return 1
            try:
                res = future.result()
                results.append(res)
                done_count = len(results)
                total_scenes = len(scene_folders)
                print(f"[ok]   [{done_count}/{total_scenes}] 第 {res[0]:03d} 幕推鏡完成 ({res[3]:.1f}s)")
                if cb:
                    ratio = done_count / max(1, total_scenes)
                    cb(done_count, total_scenes, f"推鏡渲染中 ({done_count}/{total_scenes}) 第 {res[0]:03d} 幕", stage_ratio=ratio * 0.8)
            except Exception as e:
                print(f"[fail] 第 {idx:03d} 幕 ({s_dir.name}) 生成失敗：{e}", file=sys.stderr)
                executor.shutdown(wait=False, cancel_futures=True)
                return 1

    # 按 idx 嚴格排序還原鏡頭時間軸
    results.sort(key=lambda r: r[0])
    seg_videos = [r[1] for r in results]
    audio_files = [r[2] for r in results]

    # 2. 合併音訊
    if cb:
        cb(len(scene_folders), len(scene_folders), "正在合併旁白音訊軌道...", stage_ratio=0.85)
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
    if cb:
        cb(len(scene_folders), len(scene_folders), "正在串接 1080p 視訊軌道...", stage_ratio=0.90)
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

    # 4. 最終合成：視訊 + 音訊 (+ 選配 ASS 字幕燒錄)
    final_film = compose_dir / "film.mp4"

    if cb:
        cb(len(scene_folders), len(scene_folders), "正在合流輸出 1080p 成片...", stage_ratio=0.96)

    # 支援音訊音量最佳化 (預設開啟 YouTube/廣播級響度標準化，將平均音量由偏低的 -38dB 提升至標準 -14 LUFS，大幅提升清晰度且絕不破音)
    audio_cfg = job_cfg.get("audio", {}) if isinstance(job_cfg.get("audio"), dict) else {}
    volume_gain = audio_cfg.get("volume")
    use_loudnorm = audio_cfg.get("loudnorm", True)

    audio_filters: list[str] = []
    if volume_gain:
        audio_filters.append(f"volume={volume_gain}")
    if use_loudnorm:
        audio_filters.append("loudnorm=I=-14:TP=-1.5:LRA=11")

    af_args = ["-filter:a", ",".join(audio_filters)] if audio_filters else []

    if burn_subtitles:
        print("[gen]  正在合流音訊、提升音量至廣播級響度 (-14 LUFS)、燒錄 1080p ASS 字幕並輸出影片...")
        escaped_ass = str(ass_path.resolve().as_posix()).replace(":", r"\:")
        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(raw_video_mp4),
            "-i", str(narration_wav),
            "-vf", f"subtitles='{escaped_ass}'",
            *af_args,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(final_film),
        ]
    else:
        print("[gen]  [極速直通] 依設定不燒錄字幕至畫面，正在合流視訊並將音量提升至廣播級響度 (-14 LUFS)...")
        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(raw_video_mp4),
            "-i", str(narration_wav),
            "-c:v", "copy",
            *af_args,
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
        "burned_subtitles": burn_subtitles,
        "scenes_count": len(scene_folders),
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
    }
    (compose_dir / "film.json").write_text(json.dumps(film_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[ok]   成片合成大功告成！\n       檔案路徑：{final_film.relative_to(REPO_ROOT)}")
    return 0
