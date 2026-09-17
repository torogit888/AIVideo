from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import yaml

from aivideo.commands.check import _load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_tts(args: argparse.Namespace) -> int:
    _load_dotenv()

    job_dir = Path(args.job)
    if not job_dir.is_absolute():
        job_dir = REPO_ROOT / job_dir

    job_yaml_path = job_dir / "job.yaml"
    if not job_yaml_path.is_file():
        print(f"[fail] 找不到 job.yaml：{job_yaml_path}", file=sys.stderr)
        return 1

    with open(job_yaml_path, "r", encoding="utf-8") as f:
        job_cfg = yaml.safe_load(f) or {}

    voice_id = job_cfg.get("voice_id", "narrator_zh_tw")
    voice_yaml_path = REPO_ROOT / "assets" / "voices" / voice_id / "voice.yaml"
    if not voice_yaml_path.is_file():
        print(f"[fail] 找不到音色設定檔：{voice_yaml_path}", file=sys.stderr)
        return 1

    with open(voice_yaml_path, "r", encoding="utf-8") as f:
        voice_cfg = yaml.safe_load(f) or {}

    voice_instruct = str(voice_cfg.get("voice_instruct", "女，青年，中音调")).strip()
    steps = int(voice_cfg.get("steps", 32))
    speed = float(voice_cfg.get("speed", 1.0))
    dtype = str(voice_cfg.get("dtype", "fp16")).strip()
    attention = str(voice_cfg.get("attention", "eager")).strip()
    default_seed = int(voice_cfg.get("seed", 42))

    comfy_url = os.environ.get("COMFY_URL", "http://comfyui:8188").rstrip("/")

    # 檢查 ComfyUI 是否連得上
    try:
        with urllib.request.urlopen(f"{comfy_url}/system_stats", timeout=5) as resp:
            if resp.status >= 300:
                print(f"[fail] ComfyUI 回應狀態異常：{resp.status}", file=sys.stderr)
                return 1
    except Exception as exc:
        print(f"[fail] 無法連線至 ComfyUI ({comfy_url})：{exc}\n請確認已啟動 comfyui 容器：docker compose --profile comfyui up -d comfyui", file=sys.stderr)
        return 1

    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        print(f"[fail] 找不到 scenes 目錄：{scenes_dir}", file=sys.stderr)
        return 1

    scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])
    if not scene_folders:
        print(f"[skip] {scenes_dir} 內沒有場景資料夾", file=sys.stderr)
        return 0

    target_scene = getattr(args, "scene", None)
    count = max(1, getattr(args, "count", 1))
    draft = getattr(args, "draft", False)
    force = getattr(args, "force", False)
    keep_seed = getattr(args, "keep_seed", False)

    processed = 0
    errors = 0

    for s_dir in scene_folders:
        s_id = s_dir.name
        if target_scene and not (s_id == target_scene or s_id.startswith(f"{target_scene}_") or s_id.startswith(target_scene)):
            continue

        scene_yaml_path = s_dir / "scene.yaml"
        if not scene_yaml_path.is_file():
            continue

        with open(scene_yaml_path, "r", encoding="utf-8") as f:
            scene_cfg = yaml.safe_load(f) or {}

        locks = scene_cfg.get("locks", {})
        if locks.get("speech", False) and not force and not draft:
            print(f"[skip] {s_id}: 語音已鎖定 (locked)")
            continue

        narration = str(scene_cfg.get("narration", "")).strip()
        if not narration:
            print(f"[skip] {s_id}: 未提供 narration 台詞")
            continue

        takes_dir = s_dir / "takes"
        takes_dir.mkdir(parents=True, exist_ok=True)

        for _ in range(count):
            now = datetime.now(timezone.utc).astimezone()
            take_id = f"speech_{now.strftime('%Y%m%dT%H%M%S')}"

            seed = default_seed
            if getattr(args, "new_seed", False):
                seed = random.randint(10000000, 99999999)
            elif keep_seed:
                current_take = scene_cfg.get("current", {}).get("speech_take")
                if current_take:
                    prev_json = takes_dir / f"{current_take}.json"
                    if prev_json.is_file():
                        try:
                            seed = json.loads(prev_json.read_text(encoding="utf-8")).get("seed", default_seed)
                        except Exception:
                            pass

            print(f"[gen]  {s_id} 正在透過 ComfyUI (OmniVoice-bf16) 合成語音...")

            prompt_graph = {
                "1": {
                    "inputs": {
                        "model": "OmniVoice-bf16 (auto download)",
                        "text": narration,
                        "voice_instruct": voice_instruct,
                        "steps": steps,
                        "guidance_scale": 2.0,
                        "t_shift": 0.1,
                        "speed": speed,
                        "duration": 0.0,
                        "device": "cuda",
                        "dtype": dtype,
                        "attention": attention,
                        "seed": seed,
                        "position_temperature": 5.0,
                        "class_temperature": 0.0,
                        "layer_penalty_factor": 5.0,
                        "denoise": True,
                        "postprocess_output": True,
                        "keep_model_loaded": False,
                    },
                    "class_type": "OmniVoiceVoiceDesignTTS",
                    "_meta": {"title": "OmniVoice Voice Design TTS"},
                },
                "2": {
                    "inputs": {
                        "audio": ["1", 0],
                    },
                    "class_type": "PreviewAudio",
                    "_meta": {"title": "Preview Audio"},
                },
            }

            try:
                # 提交 prompt 給 ComfyUI
                req = urllib.request.Request(
                    f"{comfy_url}/prompt",
                    data=json.dumps({"prompt": prompt_graph}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                prompt_id = resp_data.get("prompt_id")
                if not prompt_id:
                    raise RuntimeError("ComfyUI 未返回 prompt_id")

                # 等待執行完成
                audio_info = None
                for _ in range(180):  # 最多等 3 分鐘
                    time.sleep(1)
                    with urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}", timeout=5) as resp:
                        hist = json.loads(resp.read().decode("utf-8"))
                    if prompt_id in hist:
                        outputs = hist[prompt_id].get("outputs", {})
                        if "2" in outputs and "audio" in outputs["2"]:
                            audio_info = outputs["2"]["audio"][0]
                            break
                        # 檢查是否有例外
                        status = hist[prompt_id].get("status", {})
                        if status.get("status_str") == "error":
                            raise RuntimeError(f"ComfyUI 執行錯誤：{status.get('messages')}")

                if not audio_info:
                    raise TimeoutError("等待 ComfyUI 語音生成逾時")

                # 下載音訊
                query = urllib.parse.urlencode({
                    "filename": audio_info["filename"],
                    "subfolder": audio_info.get("subfolder", ""),
                    "type": audio_info.get("type", "temp"),
                })
                raw_audio_url = f"{comfy_url}/view?{query}"
                with urllib.request.urlopen(raw_audio_url, timeout=30) as resp:
                    raw_bytes = resp.read()

                dest_wav = takes_dir / f"{take_id}.wav"
                dest_json = takes_dir / f"{take_id}.json"
                temp_raw = takes_dir / f"{take_id}_temp.audio"
                temp_raw.write_bytes(raw_bytes)

                # 用 ffmpeg 轉為標準 44.1kHz 16bit WAV
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(temp_raw), "-ar", "44100", "-ac", "2", str(dest_wav)],
                    check=True,
                    capture_output=True,
                )
                temp_raw.unlink(missing_ok=True)

                # 透過 ffprobe 測量精確秒數
                probe_proc = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        str(dest_wav),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                duration_sec = round(float(probe_proc.stdout.strip()), 3)

            except Exception as exc:
                print(f"[fail] {s_id} 語音合成失敗: {exc}", file=sys.stderr)
                errors += 1
                break

            meta = {
                "take_id": take_id,
                "kind": "speech",
                "engine": "omnivoice",
                "model": "OmniVoice-bf16",
                "mode": "design",
                "voice_id": voice_id,
                "voice_instruct": voice_instruct,
                "steps": steps,
                "speed": speed,
                "dtype": dtype,
                "attention": attention,
                "seed": seed,
                "duration_sec": duration_sec,
                "created_at": now.isoformat(),
            }
            dest_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            if not draft:
                shutil.copy2(dest_wav, s_dir / "speech.wav")
                shutil.copy2(dest_json, s_dir / "speech.json")
                if "current" not in scene_cfg:
                    scene_cfg["current"] = {}
                scene_cfg["current"]["speech_take"] = take_id
                with open(scene_yaml_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(scene_cfg, f, allow_unicode=True, sort_keys=False)

            print(f"[ok]   {s_id} -> {take_id}.wav ({duration_sec}s)")
            processed += 1

    print(f"\n完成！已產出 {processed} 段語音" + (f"，失敗 {errors} 場" if errors else ""))
    return 1 if errors else 0
