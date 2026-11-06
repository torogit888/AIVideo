"""下載 Illustrious-XL 官方底模與 tekjin01929 Chibi LoRA 至 ComfyUI 容器。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

CONTAINER_NAME = "aivideo-comfyui-1"

MODELS = [
    (
        "Illustrious-XL FP8 官方底模 (專為 6GB 顯存優化)",
        "checkpoints",
        "Illustrious-XL-v0.1.float8_e4m3fn.safetensors",
        "https://huggingface.co/p1atdev/Illustrious-XL-v0.1-fp8/resolve/main/Illustrious-XL-v0.1.float8_e4m3fn.safetensors",
        "約 3.5 GB",
    ),
]

LORA_FILENAME = "tekjin01929_Chibi_Style_Illust.safetensors"
LORA_CIVITAI_URL = "https://civitai.com/models/1576277/tekjin01929s-chibi-style"


def check_container():
    res = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    names = [n.strip() for n in res.stdout.splitlines() if n.strip()]
    if CONTAINER_NAME not in names:
        print(f"[錯誤] ComfyUI 容器 ({CONTAINER_NAME}) 尚未啟動！", file=sys.stderr)
        print("請先啟動服務：docker compose --profile comfyui up -d comfyui", file=sys.stderr)
        sys.exit(1)


def download_checkpoint():
    total = len(MODELS)
    for idx, (label, subfolder, filename, url, size_str) in enumerate(MODELS, start=1):
        dest_dir = f"/basedir/models/{subfolder}"
        dest_path = f"{dest_dir}/{filename}"

        # 檢查是否已存在且非空 (> 1MB)
        check_cmd = ["docker", "exec", "-u", "0", CONTAINER_NAME, "sh", "-c", f"[ -s {dest_path} ] && [ $(stat -c%s {dest_path}) -gt 1048576 ]"]
        if subprocess.run(check_cmd).returncode == 0:
            print(f"[{idx}/{total}] {label} 已存在於容器中，略過下載。")
            continue

        # 清除可能殘留的 0 byte 檔案
        subprocess.run(["docker", "exec", "-u", "0", CONTAINER_NAME, "rm", "-f", dest_path])

        print(f"\n========================================================")
        print(f"[{idx}/{total}] 正在下載 {label} ({size_str})")
        print(f"目標：{dest_path}")
        print(f"來源：{url}")
        print(f"========================================================")

        subprocess.run(["docker", "exec", "-u", "0", CONTAINER_NAME, "mkdir", "-p", dest_dir], check=True)

        cmd = [
            "docker",
            "exec",
            "-u",
            "0",
            CONTAINER_NAME,
            "wget",
            "-c",
            "--progress=bar:force",
            "-O",
            dest_path,
            url,
        ]
        ret = subprocess.run(cmd)
        if ret.returncode != 0:
            print(f"[錯誤] 下載 {filename} 失敗 (Exit code: {ret.returncode})", file=sys.stderr)
            sys.exit(ret.returncode)

        print(f"[完成] {filename} 下載成功！")


def sync_or_download_lora():
    dest_path = f"/basedir/models/loras/{LORA_FILENAME}"

    # 1. 檢查容器內是否已存在
    check_cmd = ["docker", "exec", "-u", "0", CONTAINER_NAME, "sh", "-c", f"[ -s {dest_path} ] && [ $(stat -c%s {dest_path}) -gt 1048576 ]"]
    if subprocess.run(check_cmd).returncode == 0:
        print(f"\n[LoRA] {LORA_FILENAME} 已存在於 ComfyUI 容器中！")
        return

    # 2. 智慧掃描本地下載目錄與專案目錄
    candidates = [
        Path.home() / "Downloads" / LORA_FILENAME,
        Path.home() / "Downloads" / "tekjin01929_Chibi_Style_Illust.safetensors",
        Path.cwd() / LORA_FILENAME,
        Path.cwd() / "models" / LORA_FILENAME,
    ]
    # 也模糊搜尋 Downloads 裡的 chibi*.safetensors
    down_dir = Path.home() / "Downloads"
    if down_dir.is_dir():
        for f in down_dir.glob("*chibi*.safetensors"):
            if f not in candidates:
                candidates.append(f)

    found_local: Path | None = None
    for cand in candidates:
        if cand.is_file() and cand.stat().st_size > 1024 * 1024:
            found_local = cand
            break

    if found_local:
        print(f"\n[LoRA] 在本地找到 LoRA 檔案：{found_local}")
        print(f"正在同步至 ComfyUI 容器：{dest_path} ...")
        subprocess.run(["docker", "exec", "-u", "0", CONTAINER_NAME, "mkdir", "-p", "/basedir/models/loras"], check=True)
        ret = subprocess.run(["docker", "cp", str(found_local), f"{CONTAINER_NAME}:{dest_path}"])
        if ret.returncode == 0:
            print("[完成] LoRA 檔案同步成功！")
            return
        else:
            print(f"[警告] docker cp 失敗，代碼: {ret.returncode}")

    # 3. 若本地無檔案，引導使用者下載
    print(f"\n========================================================")
    print(" 【LoRA 模型下載提示】")
    print(f" 由於 Civitai 針對 API 下載設有授權限制 (HTTP 401)，")
    print(f" 請直接在瀏覽器開啟模型頁面下載：")
    print(f" 👉 {LORA_CIVITAI_URL}")
    print(f" 點擊頁面右側的「Download」按鈕，下載檔案：{LORA_FILENAME}")
    print(f" 下載完成後存放在您的「下載 (Downloads)」資料夾即可，")
    print(f" 再次執行本腳本將自動為您複製進容器！")
    print(f"========================================================")


def main():
    print("==========================================================")
    print(" 準備配置 Illustrious-XL 底模與 tekjin01929 Chibi LoRA")
    print("==========================================================")
    check_container()

    # 1. 下載底模
    download_checkpoint()

    # 2. 同步或下載 LoRA
    sync_or_download_lora()

    print("\n==========================================================")
    print(" 處理完成！")
    print("==========================================================")


if __name__ == "__main__":
    main()
