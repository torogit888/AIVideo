from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from aivideo.gemini_image import generate_smoke_image, has_gemini_credentials

REPO_ROOT = Path(__file__).resolve().parents[2]
CUDA_SMOKE_IMAGE = "nvidia/cuda:12.6.0-base-ubuntu24.04"


def _ok(label: str, detail: str = "") -> None:
    suffix = f"  {detail}" if detail else ""
    print(f"[ok]   {label}{suffix}")


def _fail(label: str, detail: str) -> None:
    print(f"[fail] {label}  {detail}", file=sys.stderr)


def _skip(label: str, detail: str) -> None:
    print(f"[skip] {label}  {detail}")


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value

    # 若啟用了 Vertex AI，清除可能殘留的 GEMINI_API_KEY 避免 SDK 誤走 AI Studio
    if str(os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "")).strip().lower() in {"1", "true", "yes", "on"}:
        if "GEMINI_API_KEY" in os.environ and not os.environ["GEMINI_API_KEY"].startswith("ya29."):
            del os.environ["GEMINI_API_KEY"]


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_check(args: argparse.Namespace) -> int:
    _load_dotenv()
    failed = 0

    in_container = Path("/.dockerenv").exists()
    docker = shutil.which("docker")
    ffmpeg = shutil.which("ffmpeg")

    if in_container:
        _ok("pipeline 容器", "目前在 Dev Container / compose 裡")
        if ffmpeg:
            _ok("FFmpeg", ffmpeg)
        else:
            _fail("FFmpeg", "容器裡找不到 ffmpeg")
            failed += 1
        if args.gpu:
            _skip("GPU", "請在 Windows 主機跑：docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi")
    else:
        if docker:
            version = _run([docker, "version", "--format", "{{.Server.Version}}"])
            if version.returncode == 0:
                _ok("Docker", version.stdout.strip() or "running")
            else:
                _fail("Docker", version.stderr.strip() or "daemon 沒在跑。請開 Docker Desktop。")
                failed += 1
        else:
            _fail("Docker", "找不到 docker。請安裝並啟動 Docker Desktop（WSL2 backend）。")
            failed += 1
            docker = None

        if args.gpu:
            if docker is None:
                _fail("GPU", "沒有 docker，無法測 GPU。")
                failed += 1
            else:
                gpu = _run(
                    [
                        docker,
                        "run",
                        "--rm",
                        "--gpus",
                        "all",
                        CUDA_SMOKE_IMAGE,
                        "nvidia-smi",
                        "-L",
                    ],
                    timeout=300,
                )
                if gpu.returncode == 0 and "NVIDIA" in (gpu.stdout + gpu.stderr):
                    _ok("GPU", gpu.stdout.strip().splitlines()[0])
                else:
                    detail = (gpu.stderr or gpu.stdout).strip() or "nvidia-smi 失敗"
                    _fail("GPU", detail)
                    failed += 1
        else:
            _skip("GPU", "加上 --gpu 才會拉 CUDA 容器測 nvidia-smi")

    raw_prompt = getattr(args, "prompt", None)
    if isinstance(raw_prompt, list):
        prompt_text = " ".join(raw_prompt).strip()
    elif isinstance(raw_prompt, str):
        prompt_text = raw_prompt.strip()
    else:
        prompt_text = ""
    # 去除前後可能殘留的引號
    if prompt_text.startswith(('"', "'")) and prompt_text.endswith(('"', "'")) and len(prompt_text) >= 2:
        prompt_text = prompt_text[1:-1].strip()
    custom_prompt = prompt_text or SMOKE_PROMPT

    raw_neg = getattr(args, "negative_prompt", None)
    if isinstance(raw_neg, list):
        neg_text = " ".join(raw_neg).strip()
    elif isinstance(raw_neg, str):
        neg_text = raw_neg.strip()
    else:
        neg_text = ""
    if neg_text.startswith(('"', "'")) and neg_text.endswith(('"', "'")) and len(neg_text) >= 2:
        neg_text = neg_text[1:-1].strip()
    custom_negative = neg_text

    raw_ref = (getattr(args, "ref_image", None) or "").strip()
    if raw_ref.startswith(('"', "'")) and raw_ref.endswith(('"', "'")) and len(raw_ref) >= 2:
        raw_ref = raw_ref[1:-1].strip()
    ref_image_input = raw_ref or None
    denoise_val = getattr(args, "denoise", 0.75)

    custom_lora = getattr(args, "lora", None)
    if custom_lora and isinstance(custom_lora, str):
        custom_lora = custom_lora.strip(' "\'')
    custom_lora_strength = float(getattr(args, "lora_strength", 1.0) or 1.0)
    engine_val = getattr(args, "engine", "auto") or "auto"

    if not has_gemini_credentials():
        _fail(
            "Gemini 認證",
            "未設定有效認證。可用 GEMINI_API_KEY，或啟用 Vertex AI：GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION。",
        )
        failed += 1
    elif args.gemini:
        dest = REPO_ROOT / "jobs" / "_smoke" / "gemini_16x9.png"
        try:
            from aivideo.gemini_image import generate_image

            saved, _, _ = generate_image(prompt=custom_prompt, dest=dest, ref_image=ref_image_input)
            _ok("Gemini 16:9", str(saved.relative_to(REPO_ROOT)))
        except Exception as exc:  # noqa: BLE001 — 煙霧測試要把 API 錯誤原樣印出
            _fail("Gemini 16:9", str(exc))
            failed += 1
    else:
        _ok("Gemini 認證", "已設定（加上 --gemini 才真的出一張 16:9）")

    from aivideo.comfy_image import get_comfy_url
    comfy_url = get_comfy_url()
    comfy_online = False
    try:
        from urllib.request import urlopen

        with urlopen(f"{comfy_url}/system_stats", timeout=10) as resp:
            if 200 <= resp.status < 300:
                _ok("ComfyUI", comfy_url)
                comfy_online = True
            else:
                _skip("ComfyUI", f"{comfy_url} 回應 {resp.status}")
    except Exception:
        _skip(
            "ComfyUI",
            "還沒啟動。GPU 通過後再：docker compose --profile comfyui up -d comfyui",
        )

    if getattr(args, "comfy_image", False):
        dest = REPO_ROOT / "jobs" / "_smoke" / "comfyui_z_image_turbo_16x9.png"
        try:
            from aivideo.gemini_image import generate_image

            saved, _, _ = generate_image(
                prompt=custom_prompt,
                dest=dest,
                negative_prompt=custom_negative,
                model="comfyui:illustrious" if engine_val == "illustrious" else "comfyui:z-image-turbo",
                engine=engine_val,
                ref_image=ref_image_input,
                denoise=denoise_val,
                lora_name=custom_lora,
                lora_strength=custom_lora_strength,
            )
            _ok("ComfyUI Z-Image Turbo 16:9", str(saved.relative_to(REPO_ROOT)))
        except Exception as exc:  # noqa: BLE001
            _fail("ComfyUI Z-Image Turbo 16:9", str(exc))
            failed += 1

    if failed:
        print(f"\n未通過 {failed} 項。見 doc/規劃.md 的 P0。")
        return 1
    print("\nP0 這一步通過。下一步才是拉 ComfyUI、裝 OmniVoice。")
    return 0
