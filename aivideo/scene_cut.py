"""把切好的鏡頭寫回 job/scenes，保留同 id 的 takes 與 current。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from aivideo.naming import scene_folder_id, scene_title_from_narration


def apply_scene_cut(job_dir: Path, scenes: list[dict[str, Any]]) -> dict[str, int]:
    """依新鏡頭清單更新 scene.yaml。同 id 保留圖／聲／takes；多餘資料夾刪除。"""
    scenes_dir = job_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    keep_ids: set[str] = set()
    written = 0

    for idx, raw in enumerate(scenes, start=1):
        sid = str(raw.get("id") or scene_folder_id(idx))
        keep_ids.add(sid)
        s_dir = scenes_dir / sid
        s_dir.mkdir(parents=True, exist_ok=True)
        (s_dir / "takes").mkdir(parents=True, exist_ok=True)

        yaml_path = s_dir / "scene.yaml"
        existing: dict[str, Any] = {}
        if yaml_path.is_file():
            try:
                existing = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            except Exception:
                existing = {}

        narration = str(raw.get("narration") or existing.get("narration") or "")
        title = str(raw.get("title") or "").strip() or scene_title_from_narration(narration)
        existing.pop("visual_concept", None)
        existing.update(
            {
                "id": sid,
                "index": int(raw.get("index") or idx),
                "title": title,
                "narration": narration,
                "image_prompt": str(raw.get("image_prompt") or existing.get("image_prompt") or ""),
                "act_index": int(raw.get("act_index") or existing.get("act_index") or 0),
                "act_title": str(raw.get("act_title") or existing.get("act_title") or ""),
            }
        )
        if "image_negative" not in existing:
            existing["image_negative"] = ""
        if "locks" not in existing:
            existing["locks"] = {"speech": False, "image": False}
        if "current" not in existing:
            existing["current"] = {"speech_take": None, "image_take": None}
        if raw.get("pip_query"):
            pip = existing.get("pip") if isinstance(existing.get("pip"), dict) else {}
            pip.setdefault("enabled", False)
            pip.setdefault("image", "pip.png")
            pip.setdefault("position", "right-center")
            pip.setdefault("mode", "pip")
            pip.setdefault("scale", 0.24)
            pip.setdefault("border", 5)
            pip["query"] = raw["pip_query"]
            existing["pip"] = pip

        yaml_path.write_text(
            yaml.safe_dump(existing, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        written += 1

    removed = 0
    for child in list(scenes_dir.iterdir()):
        if child.is_dir() and child.name not in keep_ids:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1

    return {"written": written, "removed": removed}
