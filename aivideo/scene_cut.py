"""把切好的鏡頭寫回 job/scenes，保留同 id 的 takes 與 current。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from aivideo.naming import scene_folder_id, scene_title_from_narration


def apply_scene_cut(
    job_dir: Path,
    scenes: list[dict[str, Any]],
    clear_existing: bool = False,
) -> dict[str, int]:
    """依新鏡頭清單更新 scene.yaml。若 clear_existing=True 則先清空舊 scenes 與 compose 再全新寫入。"""
    scenes_dir = job_dir / "scenes"
    removed = 0

    if clear_existing:
        if scenes_dir.is_dir():
            removed = sum(1 for c in scenes_dir.iterdir() if c.is_dir())
            shutil.rmtree(scenes_dir, ignore_errors=True)
        compose_dir = job_dir / "compose"
        if compose_dir.is_dir():
            shutil.rmtree(compose_dir, ignore_errors=True)

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
        has_new_act = "act_index" in raw and raw.get("act_index") is not None
        new_act_idx = int(raw.get("act_index") or 0) if has_new_act else int(existing.get("act_index") or 0)
        new_act_title = (
            str(raw.get("act_title") or "")
            if has_new_act or ("act_title" in raw and raw.get("act_title") is not None)
            else str(existing.get("act_title") or "")
        )
        existing.update(
            {
                "id": sid,
                "index": int(raw.get("index") or idx),
                "title": title,
                "narration": narration,
                "image_prompt": str(raw.get("image_prompt") or existing.get("image_prompt") or ""),
                "character_ids": (
                    list(raw["character_ids"])
                    if isinstance(raw.get("character_ids"), list)
                    else list(existing.get("character_ids") or [])
                ),
                "act_index": new_act_idx,
                "act_title": new_act_title,
            }
        )
        if "image_negative" not in existing:
            existing["image_negative"] = ""
        if "locks" not in existing:
            existing["locks"] = {"speech": False, "image": False}
        if "current" not in existing:
            existing["current"] = {"speech_take": None, "image_take": None}
        if raw.get("pip_query"):
            q_val = str(raw["pip_query"]).strip()
            pip = existing.get("pip") if isinstance(existing.get("pip"), dict) else {}
            prev_q = str(pip.get("query") or "").strip()
            from aivideo.auto_pip import infer_pip_mode

            ai_mode = str(raw.get("pip_mode") or "").strip().lower()
            ai_mtype = str(raw.get("pip_media_type") or "").strip().lower()

            # 新分鏡或考據詞變更且尚無成圖時，預設開啟考據
            if "enabled" not in pip or (prev_q != q_val and not (s_dir / "pip.png").is_file() and not (s_dir / "pip.mp4").is_file()):
                pip["enabled"] = True
            pip.setdefault("image", "pip.png")
            pip.setdefault("position", "right-center")
            if ai_mode in ("pip", "spotlight", "broll"):
                pip["mode"] = ai_mode
            elif not pip.get("mode") or prev_q != q_val:
                pip["mode"] = infer_pip_mode(q_val, narration)
            if ai_mtype in ("video", "image"):
                pip["media_type"] = ai_mtype
            elif pip.get("mode") == "broll":
                pip["media_type"] = "video"
            else:
                pip.setdefault("media_type", "image")
            pip.setdefault("scale", 0.24)
            pip.setdefault("border", 5)
            pip["query"] = q_val
            existing["pip"] = pip

        yaml_path.write_text(
            yaml.safe_dump(existing, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        written += 1

    for child in list(scenes_dir.iterdir()):
        if child.is_dir() and child.name not in keep_ids:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1

    return {"written": written, "removed": removed}


_CTA_KEYWORDS = (
    "訂閱", "订阅", "按讚", "按赞", "點個喜歡", "点个赞", "點讚", "点赞",
    "小鈴鐺", "小铃铛", "開啟小鈴鐺", "開啟鈴鐺", "开启小铃铛",
    "分享", "留言", "追蹤", "关注", "下期見", "下一期", "下期再見",
    "下集", "下回", "敬請期待", "subscribe", "like and subscribe",
)


def is_cta_line(line: str) -> bool:
    """判斷一行台詞是否為頻道訂閱、按讚等片尾收尾宣傳詞。"""
    l = line.lower()
    return any(k in l for k in _CTA_KEYWORDS)


def merge_trailing_cta_chunks(chunks: list[list[str]]) -> list[list[str]]:
    """
    若腳本末尾最後一幕主要為頻道訂閱、按讚、開啟小鈴鐺等呼籲語 (CTA)，
    自動將其合併吸收到故事最後一幕，避免為訂閱詞多生成一個孤立無意義的新分鏡。
    """
    if len(chunks) <= 1:
        return chunks

    while len(chunks) > 1:
        last_chunk = chunks[-1]
        cta_count = sum(1 for line in last_chunk if is_cta_line(line))
        if cta_count > 0 and (cta_count == len(last_chunk) or len(last_chunk) <= 3):
            chunks[-2].extend(last_chunk)
            chunks.pop()
        else:
            break

    return chunks

