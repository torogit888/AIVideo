from __future__ import annotations

import argparse
import sys

from aivideo.commands.check import run_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aivideo",
        description="字幕、語音、圖片合成影片。第一版先用 check 確認環境。",
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

    for name, help_text in (
        ("parse", "把 script.md 切成場景（尚未實作）"),
        ("tts", "產出旁白語音（尚未實作）"),
        ("images", "Gemini 出圖（尚未實作）"),
        ("srt", "依語音時長寫字幕（尚未實作）"),
        ("compose", "FFmpeg 成片（尚未實作）"),
        ("run", "缺什麼補什麼（尚未實作）"),
        ("regen", "單場重產（尚未實作）"),
        ("lock", "鎖定產物（尚未實作）"),
        ("unlock", "解除鎖定（尚未實作）"),
        ("select", "選定某個 take（尚未實作）"),
        ("preview", "重產 preview.html（尚未實作）"),
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
