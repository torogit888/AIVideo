from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aivideo.youtube_uploader import (
    generate_youtube_chapters,
    get_auth_status,
    upload_video_to_youtube,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_youtube(args: argparse.Namespace) -> int:
    job_path = Path(args.job).resolve()
    if not job_path.is_dir():
        print(f"錯誤：找不到專案目錄：{job_path}", file=sys.stderr)
        return 1

    film_path = job_path / "compose" / "film.mp4"
    if not film_path.is_file():
        print(f"錯誤：找不到成片檔案 {film_path}，請先執行 aivideo compose 合成成片。", file=sys.stderr)
        return 1

    status = get_auth_status()
    if not status.get("is_authenticated"):
        print("錯誤：尚未通過 YouTube OAuth 授權。", file=sys.stderr)
        print("請先將 Google Cloud client_secret.json 放入 assets/credentials/ 或於 Web Studio 介面完成登入授權。", file=sys.stderr)
        return 1

    channel = status.get("channel")
    if channel:
        print(f"[YouTube] 已綁定發布頻道：{channel.get('title')} ({channel.get('custom_url') or channel.get('id')})")

    # 標題
    title = args.title
    if not title:
        title = job_path.name
        job_yaml = job_path / "job.yaml"
        if job_yaml.is_file():
            try:
                import yaml
                with open(job_yaml, "r", encoding="utf-8") as f:
                    yd = yaml.safe_load(f)
                    if yd and yd.get("title"):
                        title = yd["title"]
            except Exception:
                pass

    # 說明
    desc = args.description or ""
    if not desc:
        outline_file = job_path / "outline.md"
        parts = []
        if outline_file.is_file():
            parts.append(outline_file.read_text(encoding="utf-8").strip())
        parts.append(f"#{title.split()[0] if title else '說書'} #歷史秘辛 #紀錄片")
        desc = "\n\n".join(parts)

    tags = args.tags.split(",") if args.tags else ["說書人", "歷史秘辛", "紀錄片"]

    print(f"[YouTube] 準備上傳：{title}")
    print(f"[YouTube] 隱私狀態：{args.privacy}")
    print(f"[YouTube] 掛載字幕：{not args.no_subtitles}")
    print(f"[YouTube] 設定縮圖：{not args.no_thumbnail}")

    def progress_callback(pct: float, msg: str):
        bar_len = 30
        filled = int(round(bar_len * pct))
        bar = "=" * filled + "-" * (bar_len - filled)
        sys.stdout.write(f"\r[{bar}] {int(pct * 100)}% - {msg}")
        sys.stdout.flush()

    try:
        res = upload_video_to_youtube(
            job_dir=job_path,
            title=title,
            description=desc,
            tags=tags,
            privacy_status=args.privacy,
            upload_subtitles=not args.no_subtitles,
            upload_thumbnail=not args.no_thumbnail,
            progress_callback=progress_callback,
        )
        print("\n\n🎉 YouTube 發布成功！")
        print(f"🎬 觀看連結：{res['video_url']}")
        print(f"🛠️ Studio 管理頁面：{res['studio_url']}")
        return 0
    except Exception as e:
        print(f"\n\n❌ 上傳失敗：{e}", file=sys.stderr)
        return 1
