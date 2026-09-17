from __future__ import annotations

import argparse
import sys

from aivideo.commands.check import run_check
from aivideo.commands.compose import run_compose
from aivideo.commands.images import run_images
from aivideo.commands.preview import run_preview
from aivideo.commands.srt import run_srt
from aivideo.commands.tts import run_tts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aivideo",
        description="字幕、語音、圖片合成影片。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="檢查 Docker、GPU、Gemini 金鑰")
    check.add_argument(
        "--gpu",
        action="store_true",
        help="用小型 CUDA 容器跑 nvidia-smi（會拉映像，約數百 MB）",
    )
    check.add_argument(
        "--gemini",
        action="store_true",
        help="用 Gemini 產出一張 16:9 煙霧測試圖到 jobs/_smoke/",
    )
    check.set_defaults(func=run_check)

    images = sub.add_parser("images", help="使用 Gemini 產生場景 16:9 畫面")
    images.add_argument("--job", required=True, help="Job 目錄路徑，例如 jobs/20260916_roman_telescope")
    images.add_argument("--scene", help="指定單一場景 id 或前綴，例如 001 或 001_yuzhou_miji")
    images.add_argument("--count", type=int, default=1, help="每場抽取的 take 數量（預設 1）")
    images.add_argument("--new-seed", action="store_true", default=True, help="使用新 seed（預設）")
    images.add_argument("--keep-seed", action="store_true", help="沿用上一張 take 的 seed")
    images.add_argument("--draft", action="store_true", help="僅存入 takes/，不覆蓋 current 與 scene.yaml")
    images.add_argument("--force", action="store_true", help="強制重新產生，即使被鎖定（locked）")
    images.set_defaults(func=run_images)

    tts = sub.add_parser("tts", help="使用 ComfyUI (OmniVoice) 產生場景旁白語音")
    tts.add_argument("--job", required=True, help="Job 目錄路徑，例如 jobs/20260916_roman_telescope")
    tts.add_argument("--scene", help="指定單一場景 id 或前綴，例如 001 或 001_yuzhou_miji")
    tts.add_argument("--count", type=int, default=1, help="每場抽取的 take 數量（預設 1）")
    tts.add_argument("--new-seed", action="store_true", help="使用隨機新 seed")
    tts.add_argument("--keep-seed", action="store_true", help="沿用上一張 take 的 seed")
    tts.add_argument("--draft", action="store_true", help="僅存入 takes/，不覆蓋 current 與 scene.yaml")
    tts.add_argument("--force", action="store_true", help="強制重新產生，即使被鎖定（locked）")
    tts.set_defaults(func=run_tts)

    srt = sub.add_parser("srt", help="依語音真實時長產生 timeline.srt 字幕檔")
    srt.add_argument("--job", required=True, help="Job 目錄路徑，例如 jobs/20260916_roman_telescope")
    srt.set_defaults(func=run_srt)

    compose = sub.add_parser("compose", help="使用 FFmpeg 合成 1080p 影片 (Ken Burns 推鏡 + 旁白 + 字幕)")
    compose.add_argument("--job", required=True, help="Job 目錄路徑，例如 jobs/20260916_roman_telescope")
    compose.set_defaults(func=run_compose)

    preview = sub.add_parser("preview", help="產生 preview.html 故事板網頁檢視")
    preview.add_argument("--job", required=True, help="Job 目錄路徑，例如 jobs/20260916_roman_telescope")
    preview.set_defaults(func=run_preview)

    for name, help_text in (
        ("parse", "把 script.md 切成場景（尚未實作）"),
        ("run", "缺什麼補什麼（尚未實作）"),
        ("regen", "單場重產（尚未實作）"),
        ("lock", "鎖定產物（尚未實作）"),
        ("unlock", "解除鎖定（尚未實作）"),
        ("select", "選定某個 take（尚未實作）"),
    ):
        pending = sub.add_parser(name, help=help_text)
        pending.set_defaults(func=_not_implemented, pending_name=name)

    return parser


def _not_implemented(args: argparse.Namespace) -> int:
    print(f"「{args.pending_name}」還沒做。請先跑：aivideo check --gpu --gemini", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
