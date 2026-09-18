from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

from aivideo.commands.check import _load_dotenv
from aivideo.gemini_image import generate_image, has_gemini_credentials

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_images(args: argparse.Namespace, progress_callback=None) -> int:
    _load_dotenv()

    callback = progress_callback or getattr(args, "progress_callback", None)

    if not has_gemini_credentials():
        print("[fail] 未設定有效的 Gemini API 認證（請檢查 .env）", file=sys.stderr)
        return 1

    job_dir = Path(args.job)
    if not job_dir.is_absolute():
        job_dir = REPO_ROOT / job_dir

    job_yaml_path = job_dir / "job.yaml"
    if not job_yaml_path.is_file():
        print(f"[fail] 找不到 job.yaml：{job_yaml_path}", file=sys.stderr)
        return 1

    with open(job_yaml_path, "r", encoding="utf-8") as f:
        job_cfg = yaml.safe_load(f) or {}

    style_prefix = str(job_cfg.get("style_prefix", "")).strip()
    img_cfg = job_cfg.get("image", {})
    model = img_cfg.get("model", "gemini-3.1-flash-image")
    resolution = img_cfg.get("resolution", "1K")
    aspect_ratio = img_cfg.get("aspect_ratio", "16:9")

    # 檢查專案是否啟用主體定裝參考圖 (Visual Reference Conditioning)
    visual_anchors = job_cfg.get("visual_anchors", {})
    use_image_ref = visual_anchors.get("use_image_reference", True)
    hero_anchor_path = job_dir / "hero_anchor.png"
    ref_image_to_use = hero_anchor_path if (use_image_ref and hero_anchor_path.is_file()) else None
    if ref_image_to_use:
        print(f"[info] 已掛載主體定裝參考圖進行多模態一致性生圖：{ref_image_to_use.name}")

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

    target_folders = [
        s for s in scene_folders
        if not target_scene or (s.name == target_scene or s.name.startswith(f"{target_scene}_") or s.name.startswith(target_scene))
    ]
    total_targets = len(target_folders)

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
        if locks.get("image", False) and not force and not draft:
            print(f"[skip] {s_id}: 圖片已鎖定 (locked)")
            if callback:
                callback(processed, total_targets, f"[{processed}/{total_targets}] {s_id} 跳過（已鎖定）")
            continue

        prompt = str(scene_cfg.get("image_prompt", "")).strip()
        if not prompt:
            print(f"[skip] {s_id}: 未提供 image_prompt")
            continue

        full_prompt = f"{style_prefix}，{prompt}".strip("，") if style_prefix else prompt
        takes_dir = s_dir / "takes"
        takes_dir.mkdir(parents=True, exist_ok=True)

        for _ in range(count):
            now = datetime.now(timezone.utc).astimezone()
            take_id = f"image_{now.strftime('%Y%m%dT%H%M%S')}"

            seed = None
            if keep_seed:
                # 嘗試從先前的 take 抓 seed
                current_take = scene_cfg.get("current", {}).get("image_take")
                if current_take:
                    prev_json = takes_dir / f"{current_take}.json"
                    if prev_json.is_file():
                        try:
                            seed = json.loads(prev_json.read_text(encoding="utf-8")).get("seed")
                        except Exception:
                            pass
            if seed is None:
                seed = random.randint(10000000, 99999999)

            dest_png = takes_dir / f"{take_id}.png"
            dest_json = takes_dir / f"{take_id}.json"

            print(f"[gen]  {s_id} 正在呼叫 Gemini ({model}) 出圖...")
            try:
                saved_path, model_used, used_seed = generate_image(
                    prompt=full_prompt,
                    dest=dest_png,
                    aspect_ratio=aspect_ratio,
                    image_size=resolution,
                    model=model,
                    seed=seed,
                    ref_image=ref_image_to_use,
                )
            except Exception as exc:
                print(f"[fail] {s_id} 出圖失敗: {exc}", file=sys.stderr)
                errors += 1
                break

            meta = {
                "take_id": take_id,
                "kind": "image",
                "backend": "gemini",
                "model": model_used,
                "seed": used_seed,
                "prompt": full_prompt,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "width": 1920,
                "height": 1080,
                "created_at": now.isoformat(),
            }
            dest_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            if not draft:
                shutil.copy2(dest_png, s_dir / "image.png")
                shutil.copy2(dest_json, s_dir / "image.json")
                if "current" not in scene_cfg:
                    scene_cfg["current"] = {}
                scene_cfg["current"]["image_take"] = take_id
                with open(scene_yaml_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(scene_cfg, f, allow_unicode=True, sort_keys=False)

            print(f"[ok]   {s_id} -> {take_id}.png")
            processed += 1
            if callback:
                callback(processed, total_targets, f"[{processed}/{total_targets}] {s_id} 畫面已產出")

    print(f"\n完成！已產出 {processed} 張圖片" + (f"，失敗 {errors} 場" if errors else ""))
    return 1 if errors else 0
