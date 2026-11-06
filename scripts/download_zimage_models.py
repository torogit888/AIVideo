"""下載 Z-Image Turbo 官方模型檔案至 ComfyUI 容器。"""

from __future__ import annotations

import subprocess
import sys
import time

CONTAINER_NAME = "aivideo-comfyui-1"

MODELS = [
    (
        "VAE",
        "vae",
        "ae.safetensors",
        "https://huggingface.co/Comfy-Org/Z-Image-Turbo/resolve/main/split_files/vae/ae.safetensors",
        "約 335 MB",
    ),
    (
        "Text Encoder",
        "text_encoders",
        "qwen_3_4b.safetensors",
        "https://huggingface.co/Comfy-Org/Z-Image-Turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
        "約 8.04 GB",
    ),
    (
        "Diffusion Model",
        "diffusion_models",
        "z_image_turbo_bf16.safetensors",
        "https://huggingface.co/Comfy-Org/Z-Image-Turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
        "約 12.3 GB",
    ),
]


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


def download_file(label: str, subfolder: str, filename: str, url: str, size_str: str, index: int, total: int):
    dest_dir = f"/basedir/models/{subfolder}"
    dest_path = f"{dest_dir}/{filename}"

    # 檢查是否已存在且非空
    check_cmd = ["docker", "exec", "-u", "0", CONTAINER_NAME, "test", "-s", dest_path]
    if subprocess.run(check_cmd).returncode == 0:
        print(f"[{index}/{total}] {label} ({filename}) 已存在於容器中，略過下載。")
        return

    print(f"\n========================================================")
    print(f"[{index}/{total}] 正在下載 {label} ({size_str})")
    print(f"目標：{dest_path}")
    print(f"來源：{url}")
    print(f"========================================================")

    # 確保目錄存在
    subprocess.run(["docker", "exec", "-u", "0", CONTAINER_NAME, "mkdir", "-p", dest_dir], check=True)

    # 使用 wget 支援斷點續傳與進度
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


def main():
    print("==========================================================")
    print(" 準備下載 Z-Image Turbo 官方模型檔案至 ComfyUI (約 20.7 GB)")
    print("==========================================================")
    check_container()

    total = len(MODELS)
    for idx, (label, subfolder, filename, url, size_str) in enumerate(MODELS, start=1):
        download_file(label, subfolder, filename, url, size_str, idx, total)

    print("\n==========================================================")
    print(" [成功] 所有 Z-Image Turbo 模型已下載完成！")
    print("==========================================================")


if __name__ == "__main__":
    main()
