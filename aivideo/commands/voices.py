from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_voices(args: argparse.Namespace) -> int:
    voices_dir = REPO_ROOT / "assets" / "voices"
    if not voices_dir.is_dir():
        print(f"[fail] 找不到音色角色庫目錄：{voices_dir}", file=sys.stderr)
        return 1

    voice_folders = sorted([p for p in voices_dir.iterdir() if p.is_dir()])
    if not voice_folders:
        print("[warn] assets/voices/ 內尚無音色角色資料夾。")
        return 0

    print("=" * 70)
    print("🎙️ AIVideo 音色角色庫清單 (Assets Voices)")
    print("=" * 70)

    for v_dir in voice_folders:
        v_id = v_dir.name
        yaml_path = v_dir / "voice.yaml"
        wav_path = v_dir / "reference.wav"
        txt_path = v_dir / "reference.txt"

        cfg = {}
        if yaml_path.is_file():
            try:
                cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass

        name = cfg.get("display_name", v_id)
        mode = cfg.get("mode", "design")
        engine = cfg.get("engine", "omnivoice")

        # 檢查音訊
        wav_status = "[未提供]"
        if wav_path.is_file():
            try:
                proc = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(wav_path)],
                    capture_output=True, text=True, check=True,
                )
                dur = round(float(proc.stdout.strip()), 2)
                wav_status = f"{dur}s [就緒]"
            except Exception:
                wav_status = "[存在但無法測量]"

        # 檢查逐字稿
        txt_status = "[未提供]"
        txt_preview = ""
        if txt_path.is_file():
            try:
                txt_content = txt_path.read_text(encoding="utf-8").strip()
                txt_status = f"{len(txt_content)}字 [就緒]"
                txt_preview = (txt_content[:28] + "...") if len(txt_content) > 28 else txt_content
            except Exception:
                txt_status = "[讀取失敗]"

        print(f"\n【{v_id}】 · {name}")
        print(f"  模式: {mode.upper()}  |  引擎: {engine}")
        print(f"  參考音檔 (reference.wav): {wav_status}")
        print(f"  參考逐字稿 (reference.txt): {txt_status}")
        if txt_preview:
            print(f"  逐字稿內容: 「{txt_preview}」")

    print("\n" + "=" * 70)
    print("💡 使用方式：在任何 job.yaml 中指定 voice_id 即可使用該音色（例如 voice_id: narrator_male）")
    print("=" * 70)
    return 0
