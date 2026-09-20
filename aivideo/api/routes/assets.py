from __future__ import annotations

from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException
import yaml

from aivideo.api.schemas import (
    AssetStyle,
    AssetTone,
    AssetVoice,
    UpdateStyleRequest,
)
from aivideo.story_generator import (
    delete_style_preset,
    load_style_presets,
    save_style_preset,
)

router = APIRouter(prefix="/assets", tags=["全域素材庫"])
REPO_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = REPO_ROOT / "assets"


@router.get("/tones", response_model=List[AssetTone])
def list_tones() -> List[AssetTone]:
    tones_dir = ASSETS_DIR / "tones"
    if not tones_dir.is_dir():
        return []

    results: List[AssetTone] = []
    for f in sorted(tones_dir.glob("*.md")):
        if f.name.upper() == "README.MD":
            continue
        content = f.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        title = lines[0].lstrip("#").strip() if lines else f.stem
        # 尋找前段摘要
        summary = ""
        for line in lines[1:]:
            if line.startswith("#"):
                continue
            if line:
                summary = line[:80] + ("..." if len(line) > 80 else "")
                break

        results.append(
            AssetTone(
                id=f.stem,
                title=title,
                summary=summary or "專業說書人口吻範本",
                content=content,
            )
        )
    return results


@router.get("/voices", response_model=List[AssetVoice])
def list_voices() -> List[AssetVoice]:
    voices_dir = ASSETS_DIR / "voices"
    if not voices_dir.is_dir():
        return []

    results: List[AssetVoice] = []
    for d in sorted(voices_dir.iterdir()):
        if not d.is_dir():
            continue
        yaml_file = d / "voice.yaml"
        if not yaml_file.is_file():
            continue

        try:
            cfg = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            vid = cfg.get("id", d.name)
            name = cfg.get("display_name", d.name)
            lang = "中文 (普通話/國語)"
            gender = "女性" if "female" in vid else ("男性" if "male" in vid else "中性")

            ref_txt = None
            ref_txt_path = d / "reference.txt"
            if ref_txt_path.is_file():
                ref_txt = ref_txt_path.read_text(encoding="utf-8").strip()

            sample_url = None
            if (d / "reference.wav").is_file():
                sample_url = f"/media/assets/voices/{d.name}/reference.wav"
            elif (d / "reference.mp3").is_file():
                sample_url = f"/media/assets/voices/{d.name}/reference.mp3"

            results.append(
                AssetVoice(
                    id=vid,
                    name=name,
                    language=lang,
                    gender=gender,
                    reference_text=ref_txt,
                    audio_sample_url=sample_url,
                )
            )
        except Exception:
            continue
    return results


@router.get("/styles", response_model=List[AssetStyle])
def list_styles() -> List[AssetStyle]:
    presets = load_style_presets()
    results: List[AssetStyle] = []

    for sid, cfg in presets.items():
        prev_url = None
        raw_prev = cfg.get("preview", "")
        if raw_prev:
            prev_url = f"/media/{raw_prev}"

        # 智慧推斷 tag
        tags = []
        name = cfg.get("name", sid)
        desc = cfg.get("description", "")
        if "動畫" in name or "動漫" in desc:
            tags.append("動畫")
        if "寫實" in name or "寫實" in desc or "科幻" in desc:
            tags.append("寫實")
        if "手繪" in desc or "水彩" in desc:
            tags.append("手繪")
        if not tags:
            tags.append("藝術")

        results.append(
            AssetStyle(
                id=sid,
                name=name,
                description=desc,
                tags=tags,
                prefix=cfg.get("prefix", ""),
                negative=cfg.get("negative", ""),
                preview_url=prev_url,
            )
        )
    return results


@router.put("/styles/{style_id}", response_model=AssetStyle)
def update_style(style_id: str, req: UpdateStyleRequest) -> AssetStyle:
    presets = load_style_presets()
    if style_id not in presets:
        raise HTTPException(status_code=404, detail="找不到指定風格")

    current = presets[style_id]
    current["name"] = req.name
    current["description"] = req.description
    current["prefix"] = req.prefix
    if req.negative is not None:
        current["negative"] = req.negative

    save_style_preset(style_id, current)

    raw_prev = current.get("preview", "")
    prev_url = f"/media/{raw_prev}" if raw_prev else None

    return AssetStyle(
        id=style_id,
        name=current["name"],
        description=current["description"],
        tags=req.tags or ["自訂"],
        prefix=current["prefix"],
        negative=current["negative"],
        preview_url=prev_url,
    )
