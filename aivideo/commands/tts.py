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
import re
import yaml
import requests
import zhconv

from aivideo.commands.check import _load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def split_sentences(text: str) -> list[str]:
    """將台詞以標點符號與換行切分為句子，保留標點與引號，避免拆散省略號與孤立引號。"""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    sentences: list[str] = []
    for line in lines:
        parts = re.split(r"([。！？!?][」”』\)]*)", line)
        for i in range(0, len(parts), 2):
            text_part = parts[i].strip()
            punct_part = parts[i + 1].strip() if i + 1 < len(parts) else ""
            sent = (text_part + punct_part).strip()
            if sent:
                sentences.append(sent)

    return sentences or [text.strip()]


def _synthesize_sentence(
    text_cn: str,
    voice_instruct: str,
    steps: int,
    speed: float,
    dtype: str,
    attention: str,
    seed: int,
    pos_temp: float,
    class_temp: float,
    comfy_url: str,
    mode: str = "design",
    ref_audio_name: str | None = None,
    ref_text_cn: str = "",
    instruct: str = "",
) -> bytes:
    if mode == "clone" and ref_audio_name:
        prompt_graph = {
            "1": {
                "inputs": {"audio": ref_audio_name},
                "class_type": "LoadAudio",
                "_meta": {"title": "Load Audio"},
            },
            "2": {
                "inputs": {
                    "model": "OmniVoice-bf16 (auto download)",
                    "text": text_cn,
                    "ref_audio": ["1", 0],
                    "ref_text": ref_text_cn,
                    "steps": steps,
                    "guidance_scale": 2.0,
                    "t_shift": 0.1,
                    "speed": speed,
                    "duration": 0.0,
                    "device": "cuda",
                    "dtype": dtype,
                    "attention": attention,
                    "seed": seed,
                    "position_temperature": pos_temp,
                    "class_temperature": class_temp,
                    "layer_penalty_factor": 5.0,
                    "denoise": True,
                    "preprocess_prompt": True,
                    "postprocess_output": True,
                    "keep_model_loaded": False,
                    "instruct": instruct,
                },
                "class_type": "OmniVoiceVoiceCloneTTS",
                "_meta": {"title": "Voice Clone TTS"},
            },
            "3": {
                "inputs": {"audio": ["2", 0]},
                "class_type": "PreviewAudio",
                "_meta": {"title": "Preview Audio"},
            },
        }
    else:
        prompt_graph = {
            "1": {
                "inputs": {
                    "model": "OmniVoice-bf16 (auto download)",
                    "text": text_cn,
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
                    "position_temperature": pos_temp,
                    "class_temperature": class_temp,
                    "layer_penalty_factor": 5.0,
                    "denoise": True,
                    "postprocess_output": True,
                    "keep_model_loaded": False,
                },
                "class_type": "OmniVoiceVoiceDesignTTS",
                "_meta": {"title": "OmniVoice Voice Design TTS"},
            },
            "2": {
                "inputs": {"audio": ["1", 0]},
                "class_type": "PreviewAudio",
                "_meta": {"title": "Preview Audio"},
            },
        }

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

    audio_info = None
    for _ in range(180):
        time.sleep(1)
        with urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}", timeout=5) as resp:
            hist = json.loads(resp.read().decode("utf-8"))
        if prompt_id in hist:
            outputs = hist[prompt_id].get("outputs", {})
            for node_id, node_data in outputs.items():
                if isinstance(node_data, dict) and "audio" in node_data and node_data["audio"]:
                    audio_info = node_data["audio"][0]
                    break
            if audio_info:
                break
            status = hist[prompt_id].get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI 執行錯誤：{status.get('messages')}")

    if not audio_info:
        raise TimeoutError("等待 ComfyUI 語音生成逾時")

    query = urllib.parse.urlencode({
        "filename": audio_info["filename"],
        "subfolder": audio_info.get("subfolder", ""),
        "type": audio_info.get("type", "temp"),
    })
    with urllib.request.urlopen(f"{comfy_url}/view?{query}", timeout=30) as resp:
        return resp.read()


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

    mode = str(voice_cfg.get("mode", "design")).strip().lower()
    voice_instruct = str(voice_cfg.get("voice_instruct", "女，青年，中音调")).strip()
    instruct = str(voice_cfg.get("instruct", "")).strip()
    steps = int(voice_cfg.get("steps", 32))
    raw_speed = float(voice_cfg.get("speed", 1.0))
    if raw_speed < 0.5 or raw_speed > 2.0:
        clamped_speed = max(0.5, min(2.0, raw_speed))
        print(f"[warn] speed 設定值 {raw_speed} 超出 OmniVoice 允許範圍 (0.5 ~ 2.0)，已自動校正為 {clamped_speed}")
        speed = clamped_speed
    else:
        speed = raw_speed

    dtype = str(voice_cfg.get("dtype", "fp16")).strip()
    attention = str(voice_cfg.get("attention", "eager")).strip()
    default_seed = int(voice_cfg.get("seed", 42))
    pos_temp = float(voice_cfg.get("position_temperature", 0.1))
    class_temp = float(voice_cfg.get("class_temperature", 0.0))

    # 在 clone 模式下檢查 instruct 是否合法，避免 ComfyUI 拋出例外拒絕執行
    if mode == "clone" and instruct:
        valid_zh_instructs = {"东北话", "中年", "中音调", "云南话", "低音调", "儿童", "四川话", "女", "宁夏话", "少年", "极低音调", "极高音调", "桂林话", "河南话", "济南话", "甘肃话", "男", "石家庄话", "老年", "耳语", "贵州话", "陕西话", "青岛话", "青年", "高音调"}
        valid_en_instructs = {"american accent", "australian accent", "british accent", "canadian accent", "child", "chinese accent", "elderly", "female", "high pitch", "indian accent", "japanese accent", "korean accent", "low pitch", "male", "middle-aged", "moderate pitch", "portuguese accent", "russian accent", "teenager", "very high pitch", "very low pitch", "whisper", "young adult"}
        if instruct not in (valid_zh_instructs | valid_en_instructs):
            print(f"[warn] instruct 設定 '{instruct}' 不在 OmniVoice 支援清單內，克隆模式已自動忽略以保留參考音原生口吻。")
            instruct = ""

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

    ref_audio_name = None
    ref_text_cn = ""
    if mode == "clone":
        voice_dir = REPO_ROOT / "assets" / "voices" / voice_id
        ref_wav_path = voice_dir / "reference.wav"
        ref_txt_path = voice_dir / "reference.txt"

        if not ref_wav_path.is_file():
            print(f"[fail] 克隆模式缺少參考音訊檔案：{ref_wav_path}\n請放置 5~15 秒乾淨口白音訊至該路徑。", file=sys.stderr)
            return 1
        if not ref_txt_path.is_file():
            print(f"[fail] 克隆模式缺少逐字稿檔案：{ref_txt_path}\n請寫入與 reference.wav 完全對齊的逐字稿。", file=sys.stderr)
            return 1

        ref_text = ref_txt_path.read_text(encoding="utf-8").strip()
        ref_text_cn = zhconv.convert(ref_text, "zh-cn")
        ref_audio_name = f"{voice_id}_reference.wav"

        # 上傳參考音訊至 ComfyUI
        with open(ref_wav_path, "rb") as f:
            up_resp = requests.post(
                f"{comfy_url}/upload/image",
                files={"image": (ref_audio_name, f)},
                data={"overwrite": "true"},
                timeout=15,
            )
        if up_resp.status_code != 200:
            print(f"[fail] 參考音訊上傳 ComfyUI 失敗：{up_resp.text}", file=sys.stderr)
            return 1
        print(f"[info] 已載入 Voice Clone 參考音色：{ref_wav_path.name}（逐字稿：{ref_text}）")

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

        sentences = split_sentences(narration)
        print(f"\n[info] {s_id} 共有 {len(sentences)} 句話，將進行逐句簡體輸入合成：")

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

            sent_wav_paths: list[Path] = []
            sentences_meta: list[dict[str, object]] = []
            current_time = 0.0
            scene_failed = False

            # 產生 0.25 秒靜音檔用於句間停頓
            silence_wav = takes_dir / f"{take_id}_silence.wav"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", "0.25", str(silence_wav),
                ],
                check=True,
                capture_output=True,
            )

            for idx, s_tc in enumerate(sentences, 1):
                # 轉成簡體中文傳給 OmniVoice
                s_cn = zhconv.convert(s_tc, "zh-cn")
                print(f"       [{idx}/{len(sentences)}] 繁: {s_tc}")
                print(f"             簡: {s_cn}")

                sent_wav = takes_dir / f"{take_id}_sent_{idx}.wav"
                sent_temp = takes_dir / f"{take_id}_sent_{idx}_raw.audio"

                try:
                    raw_bytes = _synthesize_sentence(
                        text_cn=s_cn,
                        voice_instruct=voice_instruct,
                        steps=steps,
                        speed=speed,
                        dtype=dtype,
                        attention=attention,
                        seed=seed,
                        pos_temp=pos_temp,
                        class_temp=class_temp,
                        comfy_url=comfy_url,
                        mode=mode,
                        ref_audio_name=ref_audio_name,
                        ref_text_cn=ref_text_cn,
                        instruct=instruct,
                    )
                    sent_temp.write_bytes(raw_bytes)

                    # 轉為標準 44.1kHz 16bit WAV
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", str(sent_temp), "-ar", "44100", "-ac", "2", str(sent_wav)],
                        check=True,
                        capture_output=True,
                    )
                    sent_temp.unlink(missing_ok=True)

                    # 測量該句時長
                    probe_proc = subprocess.run(
                        [
                            "ffprobe", "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1",
                            str(sent_wav),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    sent_dur = round(float(probe_proc.stdout.strip()), 3)

                    start_sec = round(current_time, 3)
                    end_sec = round(current_time + sent_dur, 3)
                    sentences_meta.append({
                        "index": idx,
                        "text": s_tc,
                        "text_cn": s_cn,
                        "start_sec": start_sec,
                        "end_sec": end_sec,
                        "duration_sec": sent_dur,
                    })

                    sent_wav_paths.append(sent_wav)
                    # 句間停頓 0.25 秒
                    sent_wav_paths.append(silence_wav)
                    current_time = end_sec + 0.25

                except Exception as exc:
                    print(f"[fail] 句子合成失敗：{exc}", file=sys.stderr)
                    scene_failed = True
                    break

            if scene_failed:
                errors += 1
                silence_wav.unlink(missing_ok=True)
                for p in sent_wav_paths:
                    p.unlink(missing_ok=True)
                continue

            # 移除最後多餘的 silence_wav
            if sent_wav_paths and sent_wav_paths[-1] == silence_wav:
                sent_wav_paths.pop()
                current_time -= 0.25

            # 合併該場景所有句子音訊
            dest_wav = takes_dir / f"{take_id}.wav"
            dest_json = takes_dir / f"{take_id}.json"
            concat_list = takes_dir / f"{take_id}_concat.txt"
            concat_list.write_text(
                "\n".join([f"file '{p.resolve().as_posix()}'" for p in sent_wav_paths]),
                encoding="utf-8",
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(dest_wav)],
                check=True,
                capture_output=True,
            )
            concat_list.unlink(missing_ok=True)
            silence_wav.unlink(missing_ok=True)
            for p in sent_wav_paths:
                if p != silence_wav:
                    p.unlink(missing_ok=True)

            total_duration_sec = round(current_time, 3)

            meta = {
                "take_id": take_id,
                "kind": "speech",
                "engine": "omnivoice",
                "model": "OmniVoice-bf16",
                "mode": mode,
                "voice_id": voice_id,
                "voice_instruct": voice_instruct,
                "steps": steps,
                "speed": speed,
                "dtype": dtype,
                "attention": attention,
                "seed": seed,
                "duration_sec": total_duration_sec,
                "sentences": sentences_meta,
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

            print(f"[ok]   {s_id} 逐句合成完畢 -> {take_id}.wav (共 {total_duration_sec}s)")
            processed += 1

    print(f"\n完成！已產出 {processed} 場語音" + (f"，失敗 {errors} 場" if errors else ""))
    return 1 if errors else 0

