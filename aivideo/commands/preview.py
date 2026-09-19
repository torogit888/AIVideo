from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def generate_preview_html(job_dir: Path) -> Path:
    job_yaml_path = job_dir / "job.yaml"
    with open(job_yaml_path, "r", encoding="utf-8") as f:
        job_cfg = yaml.safe_load(f) or {}

    title = html.escape(str(job_cfg.get("title", "影片預覽")))
    scenes_dir = job_dir / "scenes"
    compose_dir = job_dir / "compose"
    film_mp4 = compose_dir / "film.mp4"

    scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])

    rows_html: list[str] = []

    for s_dir in scene_folders:
        s_id = s_dir.name
        scene_yaml_path = s_dir / "scene.yaml"
        if not scene_yaml_path.is_file():
            continue

        with open(scene_yaml_path, "r", encoding="utf-8") as f:
            scene_cfg = yaml.safe_load(f) or {}

        s_title = html.escape(str(scene_cfg.get("title", s_id)))
        narration = html.escape(str(scene_cfg.get("narration", "")))
        prompt = html.escape(str(scene_cfg.get("image_prompt", "")))

        # 讀取 image.json
        img_meta = {}
        img_json = s_dir / "image.json"
        if img_json.is_file():
            try:
                img_meta = json.loads(img_json.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 讀取 speech.json
        speech_meta = {}
        speech_json = s_dir / "speech.json"
        if speech_json.is_file():
            try:
                speech_meta = json.loads(speech_json.read_text(encoding="utf-8"))
            except Exception:
                pass

        img_rel = f"scenes/{s_id}/image.png"
        wav_rel = f"scenes/{s_id}/speech.wav"
        pip_rel = f"scenes/{s_id}/pip.png"
        has_img = (s_dir / "image.png").is_file()
        has_wav = (s_dir / "speech.wav").is_file()
        has_pip = (s_dir / "pip.png").is_file()

        duration = speech_meta.get("duration_sec", "—")
        seed = img_meta.get("seed", "—")
        img_take = img_meta.get("take_id", "—")
        speech_take = speech_meta.get("take_id", "—")

        # 讀取 takes 清單
        takes_dir = s_dir / "takes"
        all_takes = []
        if takes_dir.is_dir():
            all_takes = sorted([p.name for p in takes_dir.glob("*.png")])

        pip_badge = '<span class="badge" style="background:#7c3aed;margin-left:6px;">🖼️ 畫中畫 PiP</span>' if has_pip else ""

        row = f"""
        <div class="scene-card">
          <div class="scene-header">
            <h3>{s_id} · {s_title}</h3>
            <div>
              {pip_badge}
              <span class="badge">時長: {duration}s</span>
            </div>
          </div>
          <div class="scene-body">
            <div class="scene-media">
              {f'<img src="{img_rel}" alt="{s_title}" class="scene-thumb" />' if has_img else '<div class="no-media">無畫面</div>'}
              {f'<div style="margin-top:6px;"><small style="color:#7c3aed;font-weight:bold;">疊加參考圖 (PiP)：</small><br><img src="{pip_rel}" alt="PiP" style="max-width:140px;border-radius:4px;border:1px solid #ccc;" /></div>' if has_pip else ''}
              {f'<audio controls src="{wav_rel}" class="scene-audio"></audio>' if has_wav else '<div class="no-media">無語音</div>'}
            </div>
            <div class="scene-meta">
              <p><strong>旁白台詞：</strong><br>{narration}</p>
              <p><strong>畫面提示詞：</strong><br><code>{prompt}</code></p>
              <div class="meta-tags">
                <span>圖 Take: {img_take}</span>
                <span>Seed: {seed}</span>
                <span>音 Take: {speech_take}</span>
                <span>歷史 Takes 數: {len(all_takes)}</span>
              </div>
            </div>
          </div>
        </div>
        """
        rows_html.append(row)

    has_film = film_mp4.is_file()
    film_section = ""
    if has_film:
        film_section = f"""
        <div class="film-container">
          <h2>🎬 最終合成成片（1080p 寬螢幕）</h2>
          <video controls class="film-player" src="compose/film.mp4"></video>
          <div class="film-actions">
            <a href="compose/film.mp4" download class="btn">下載 MP4 成片</a>
            <a href="compose/timeline.srt" download class="btn btn-secondary">下載 SRT 字幕</a>
            <a href="compose/timeline.ass" download class="btn btn-secondary">下載 ASS 字幕</a>
          </div>
        </div>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} · AIVideo 故事板預覽</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0f172a;
      color: #f1f5f9;
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    h1 {{
      font-size: 28px;
      margin-bottom: 8px;
      color: #38bdf8;
    }}
    .subtitle {{
      color: #94a3b8;
      margin-bottom: 24px;
    }}
    .film-container {{
      background: #1e293b;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 32px;
      border: 1px solid #334155;
    }}
    .film-player {{
      width: 100%;
      max-height: 540px;
      background: #000;
      border-radius: 8px;
    }}
    .film-actions {{
      margin-top: 16px;
      display: flex;
      gap: 12px;
    }}
    .btn {{
      display: inline-block;
      background: #38bdf8;
      color: #0f172a;
      text-decoration: none;
      padding: 8px 18px;
      border-radius: 6px;
      font-weight: bold;
    }}
    .btn-secondary {{
      background: #475569;
      color: #fff;
    }}
    .scene-card {{
      background: #1e293b;
      border-radius: 12px;
      margin-bottom: 20px;
      overflow: hidden;
      border: 1px solid #334155;
    }}
    .scene-header {{
      background: #334155;
      padding: 12px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .scene-header h3 {{
      margin: 0;
      font-size: 18px;
      color: #f8fafc;
    }}
    .badge {{
      background: #0284c7;
      color: #fff;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 13px;
    }}
    .scene-body {{
      display: flex;
      padding: 20px;
      gap: 24px;
    }}
    .scene-media {{
      flex: 0 0 380px;
    }}
    .scene-thumb {{
      width: 100%;
      aspect-ratio: 16/9;
      object-fit: cover;
      border-radius: 8px;
      background: #000;
    }}
    .scene-audio {{
      width: 100%;
      margin-top: 12px;
    }}
    .scene-meta {{
      flex: 1;
    }}
    .scene-meta p {{
      margin-top: 0;
      line-height: 1.6;
      font-size: 15px;
    }}
    .scene-meta code {{
      display: block;
      background: #0f172a;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      color: #cbd5e1;
      word-break: break-all;
    }}
    .meta-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
      font-size: 12px;
      color: #94a3b8;
    }}
    .meta-tags span {{
      background: #0f172a;
      padding: 4px 8px;
      border-radius: 4px;
      border: 1px solid #334155;
    }}
    @media (max-width: 768px) {{
      .scene-body {{
        flex-direction: column;
      }}
      .scene-media {{
        flex: 1;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>{title}</h1>
    <p class="subtitle">AIVideo 故事板與成片預覽系統 · 自動生成於 {scenes_dir.parent.name}</p>
    
    {film_section}

    <h2>🎞️ 各場景分鏡與語音審查</h2>
    {"".join(rows_html)}
  </div>
</body>
</html>
"""
    preview_file = job_dir / "preview.html"
    preview_file.write_text(full_html, encoding="utf-8")
    return preview_file


def run_preview(args: argparse.Namespace) -> int:
    job_dir = Path(args.job)
    if not job_dir.is_absolute():
        job_dir = REPO_ROOT / job_dir

    if not job_dir.is_dir():
        print(f"[fail] 找不到 Job 目錄：{job_dir}", file=sys.stderr)
        return 1

    preview_path = generate_preview_html(job_dir)
    print(f"[ok]   故事板預覽頁已產生：{preview_path.relative_to(REPO_ROOT)}")
    return 0
