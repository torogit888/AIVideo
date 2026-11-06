"""執行自訂測試生圖 (ComfyUI Z-Image Turbo) 並自動在 VS Code 中開啟成果。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_IMAGE = REPO_ROOT / "jobs" / "_smoke" / "comfyui_z_image_turbo_16x9.png"


def main():
    # 前置正規化 sys.argv，防禦 Windows PowerShell 偶發將參數引號黏合 (如 --denoise"0.75" 或 --denoise0.75)
    normalized_argv = []
    for arg in sys.argv[1:]:
        if arg.startswith("--denoise") and len(arg) > len("--denoise") and not arg.startswith("--denoise="):
            val = arg[len("--denoise"):].strip(' "=\'')
            normalized_argv.extend(["--denoise", val])
        elif arg.startswith("--ref-image") and len(arg) > len("--ref-image") and not arg.startswith("--ref-image="):
            val = arg[len("--ref-image"):].strip(' "=\'')
            normalized_argv.extend(["--ref-image", val])
        else:
            normalized_argv.append(arg)

    parser = argparse.ArgumentParser(description="自訂測試生圖執行腳本")
    parser.add_argument("--prefix", nargs="*", default=None, help="前置提示詞 (風格、畫風、品質)")
    parser.add_argument("--prompt", nargs="*", default=None, help="主體提示詞 (場景、主體人物、動作)")
    parser.add_argument("--suffix", nargs="*", default=None, help="後置提示詞 (構圖、光影、氛圍、視角)")
    parser.add_argument("--negative-prompt", nargs="*", default=None, help="負面提示詞 (排除元素)")
    parser.add_argument("--engine", choices=["auto", "z-image", "illustrious"], default="auto", help="生圖引擎")
    parser.add_argument("--lora", nargs="?", const="", default="", help="指定 LoRA 模型名稱")
    parser.add_argument("--lora-strength", nargs="?", const=1.0, type=float, default=1.0, help="LoRA 權重")
    parser.add_argument("--ref-image", nargs="?", const="", default="", help="參考圖路徑")
    parser.add_argument("--denoise", nargs="?", const=0.75, type=float, default=0.75, help="重繪強度")
    args = parser.parse_args(normalized_argv)

    def _clean_text(val: list[str] | str | None) -> str:
        if isinstance(val, list):
            res = " ".join(val).strip()
        elif isinstance(val, str):
            res = val.strip()
        else:
            res = ""
        if res.startswith(('"', "'")) and res.endswith(('"', "'")) and len(res) >= 2:
            res = res[1:-1].strip()
        return res

    # 1. 整理核心結構：前置 + 主體 + 後置 + 負面
    prefix_text = _clean_text(args.prefix)
    main_prompt = _clean_text(args.prompt)
    suffix_text = _clean_text(args.suffix)
    negative_text = _clean_text(args.negative_prompt)
    lora_text = _clean_text(args.lora)
    lora_strength_val = float(args.lora_strength or 1.0)

    prompt_segments = [p for p in [prefix_text, main_prompt, suffix_text] if p]
    final_prompt = ", ".join(prompt_segments) if prompt_segments else ""

    # 2. 整理參考圖 (若檔案位於專案目錄外部，自動同步至專案暫存區以供 Docker 容器存取)
    ref_image = (args.ref_image or "").strip()
    if ref_image.startswith(('"', "'")) and ref_image.endswith(('"', "'")) and len(ref_image) >= 2:
        ref_image = ref_image[1:-1].strip()

    docker_ref = ""
    if ref_image:
        host_path = Path(ref_image)
        if host_path.is_file():
            try:
                rel = host_path.relative_to(REPO_ROOT)
                docker_ref = str(rel).replace("\\", "/")
            except ValueError:
                # 參考圖位於專案目錄外（例如 C:\Users\wy\Downloads\test.png）
                smoke_dir = REPO_ROOT / "jobs" / "_smoke"
                smoke_dir.mkdir(parents=True, exist_ok=True)
                target_staged = smoke_dir / f"staged_ref{host_path.suffix}"
                shutil.copy2(host_path, target_staged)
                docker_ref = f"jobs/_smoke/{target_staged.name}"
                print(f"[info] 已自動同步外部參考圖至專案工作區：{docker_ref}")
        else:
            docker_ref = ref_image

    # 3. 組裝指令
    cmd = [
        "docker",
        "compose",
        "run",
        "--rm",
        "pipeline",
        "python",
        "-m",
        "aivideo",
        "check",
        "--comfy-image",
    ]
    if args.engine != "auto":
        cmd.extend(["--engine", args.engine])
    if final_prompt:
        cmd.extend(["--prompt", final_prompt])
    if negative_text:
        cmd.extend(["--negative-prompt", negative_text])
    if lora_text and lora_text.lower() not in ("none", "null", "無", "false", "0"):
        cmd.extend(["--lora", lora_text, "--lora-strength", str(lora_strength_val)])
    if docker_ref:
        cmd.extend(["--ref-image", docker_ref, "--denoise", str(args.denoise)])

    print("==========================================================")
    print(" 正在透過 Docker 容器執行 ComfyUI (Z-Image Turbo) 自訂生圖...")
    if prefix_text:
        print(f" [前置提示詞]: {prefix_text}")
    if main_prompt:
        print(f" [主體提示詞]: {main_prompt}")
    if suffix_text:
        print(f" [後置提示詞]: {suffix_text}")
    if final_prompt:
        print(f" [最終正向詞]: {final_prompt[:120]}...")
    if negative_text:
        print(f" [負面提示詞]: {negative_text}")
    if lora_text and lora_text.lower() not in ("none", "null", "無", "false", "0"):
        print(f" [LoRA 模型]: {lora_text} (強度: {lora_strength_val})")
    if docker_ref:
        print(f" 參考圖: {docker_ref} (Denoise: {args.denoise})")
    print("==========================================================")

    ret = subprocess.run(cmd, cwd=REPO_ROOT)
    if ret.returncode != 0:
        sys.exit(ret.returncode)

    # 4. 生圖成功後自動呼叫 VS Code 開啟圖片
    if SMOKE_IMAGE.is_file():
        code_bin = shutil.which("code") or shutil.which("code.cmd")
        if code_bin:
            subprocess.run([code_bin, "-r", str(SMOKE_IMAGE)])
            print(f"\n[完成] 成果圖已在 VS Code 分頁開啟：{SMOKE_IMAGE}")


if __name__ == "__main__":
    main()

