from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
import requests
import yaml
import zhconv

from aivideo.api.schemas import (
    AssetStyle,
    AssetTone,
    AssetVoice,
    CreateStyleRequest,
    CreateToneRequest,
    CreateVoiceRequest,
    ExtractToneRequest,
    TestVoiceRequest,
    UpdateStyleRequest,
    UpdateToneRequest,
    UpdateVoiceRequest,
)
from aivideo.commands.tts import _synthesize_sentence
from aivideo.story_generator import (
    delete_style_preset,
    extract_and_create_tone_preset,
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
        raw_text = f.read_text(encoding="utf-8")

        meta: dict = {}
        body = raw_text
        if raw_text.startswith("---"):
            parts = raw_text.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except Exception:
                    pass

        title = meta.get("name")
        summary = meta.get("description")
        tags = meta.get("tags") or []
        rec_voice = meta.get("recommended_voice_instruct")

        # Fallback if title/summary not provided in frontmatter
        if not title:
            lines = [line.strip() for line in body.splitlines() if line.strip()]
            for line in lines:
                if line.startswith("#"):
                    title = line.lstrip("#").strip()
                    break
            if not title:
                title = f.stem

        if not summary:
            lines = [line.strip() for line in body.splitlines() if line.strip()]
            for line in lines:
                if not line.startswith("#"):
                    summary = line[:80] + ("..." if len(line) > 80 else "")
                    break
            if not summary:
                summary = "專業說書人口吻範本"

        results.append(
            AssetTone(
                id=str(meta.get("id") or f.stem),
                title=str(title),
                summary=str(summary),
                tags=tags if isinstance(tags, list) else [str(tags)],
                recommended_voice_instruct=str(rec_voice) if rec_voice else None,
                content=raw_text,
            )
        )
    return results


def _sanitize_id(raw_id: str) -> str:
    cleaned = re.sub(r"[^\w\-]", "_", raw_id.strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_")


@router.post("/tones", response_model=AssetTone)
def create_tone(req: CreateToneRequest) -> AssetTone:
    tone_id = _sanitize_id(req.id)
    if not tone_id:
        raise HTTPException(status_code=400, detail="口吻 ID 不得為空")

    tones_dir = ASSETS_DIR / "tones"
    tones_dir.mkdir(parents=True, exist_ok=True)
    target_file = tones_dir / f"{tone_id}.md"
    if target_file.is_file():
        raise HTTPException(status_code=400, detail=f"口吻 ID 【{tone_id}】已存在")

    # 若內容尚未包含 Frontmatter，自動組裝標準 Frontmatter
    content = req.content.strip()
    if not content.startswith("---"):
        tags_str = ", ".join(req.tags) if req.tags else "說書, 自訂"
        rec_voice = req.recommended_voice_instruct or "女，青年，中音调"
        frontmatter = f"""---
id: {tone_id}
name: {req.title}
tags: [{tags_str}]
recommended_voice_instruct: "{rec_voice}"
description: {req.summary or '自訂說書人口吻範本'}
---

"""
        content = frontmatter + content

    target_file.write_text(content + "\n", encoding="utf-8")
    return AssetTone(
        id=tone_id,
        title=req.title,
        summary=req.summary or "自訂說書人口吻範本",
        tags=req.tags,
        recommended_voice_instruct=req.recommended_voice_instruct,
        content=content,
    )


@router.post("/tones/extract-and-save", response_model=AssetTone)
def extract_and_save_tone(req: ExtractToneRequest) -> AssetTone:
    raw_text = req.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="參考文本內容不得為空")

    try:
        result = extract_and_create_tone_preset(
            text=raw_text,
            custom_tone_id=req.tone_id,
            auto_save=req.auto_save,
            model=req.model,
            custom_title=req.title,
        )
        return AssetTone(
            id=str(result["id"]),
            title=str(result["title"]),
            summary=str(result["summary"]),
            tags=list(result["tags"]) if isinstance(result["tags"], list) else [str(result["tags"])],
            recommended_voice_instruct=str(result["recommended_voice_instruct"]) if result.get("recommended_voice_instruct") else None,
            content=str(result["content"]),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vertex AI Gemini Flash 萃取口吻失敗：{str(e)}")


@router.put("/tones/{tone_id}", response_model=AssetTone)
def update_tone(tone_id: str, req: UpdateToneRequest) -> AssetTone:
    tones_dir = ASSETS_DIR / "tones"
    target_file = tones_dir / f"{tone_id}.md"
    if not target_file.is_file():
        raise HTTPException(status_code=404, detail="找不到指定口吻範本")

    content = req.content.strip()
    # 智慧更新或附加 Frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
        else:
            body = content
    else:
        body = content

    tags_str = ", ".join(req.tags) if req.tags else "說書"
    rec_voice = req.recommended_voice_instruct or "女，青年，中音调"
    new_full_content = f"""---
id: {tone_id}
name: {req.title}
tags: [{tags_str}]
recommended_voice_instruct: "{rec_voice}"
description: {req.summary or '專業說書人口吻範本'}
---

{body}
"""
    target_file.write_text(new_full_content, encoding="utf-8")
    return AssetTone(
        id=tone_id,
        title=req.title,
        summary=req.summary,
        tags=req.tags,
        recommended_voice_instruct=req.recommended_voice_instruct,
        content=new_full_content,
    )


@router.delete("/tones/{tone_id}")
def delete_tone(tone_id: str):
    target_file = ASSETS_DIR / "tones" / f"{tone_id}.md"
    if not target_file.is_file():
        raise HTTPException(status_code=404, detail="找不到指定口吻範本")
    try:
        target_file.unlink()
        return {"success": True, "deleted_id": tone_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")


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
                rmtime = int((d / "reference.wav").stat().st_mtime)
                sample_url = f"/media/assets/voices/{d.name}/reference.wav?t={rmtime}"
            elif (d / "reference.mp3").is_file():
                rmtime = int((d / "reference.mp3").stat().st_mtime)
                sample_url = f"/media/assets/voices/{d.name}/reference.mp3?t={rmtime}"

            preview_url = None
            if (d / "preview.wav").is_file():
                pmtime = int((d / "preview.wav").stat().st_mtime)
                preview_url = f"/media/assets/voices/{d.name}/preview.wav?t={pmtime}"

            results.append(
                AssetVoice(
                    id=vid,
                    name=name,
                    language=lang,
                    gender=gender,
                    mode=cfg.get("mode", "clone"),
                    speed=float(cfg.get("speed", 1.0)),
                    position_temperature=float(cfg.get("position_temperature", 0.1)),
                    steps=int(cfg.get("steps", 32)),
                    reference_text=ref_txt,
                    audio_sample_url=sample_url,
                    test_audio_url=preview_url,
                )
            )
        except Exception:
            continue
    return results


@router.post("/voices", response_model=AssetVoice)
def create_voice(req: CreateVoiceRequest) -> AssetVoice:
    vid = _sanitize_id(req.id)
    if not vid:
        raise HTTPException(status_code=400, detail="發音人 ID 不得為空")

    voices_dir = ASSETS_DIR / "voices"
    voice_dir = voices_dir / vid
    if voice_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"發音人角色【{vid}】已存在")

    voice_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "id": vid,
        "display_name": req.name,
        "gender": req.gender,
        "engine": "omnivoice",
        "model": "OmniVoice-bf16",
        "mode": req.mode,
        "dtype": "fp16",
        "attention": "eager",
        "steps": req.steps,
        "speed": req.speed,
        "position_temperature": req.position_temperature,
    }
    (voice_dir / "voice.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    if req.reference_text.strip():
        (voice_dir / "reference.txt").write_text(req.reference_text.strip() + "\n", encoding="utf-8")

    sample_url = None
    if req.audio_base64:
        try:
            audio_data = req.audio_base64
            if "," in audio_data:
                audio_data = audio_data.split(",", 1)[1]
            raw_audio = base64.b64decode(audio_data)
            (voice_dir / "reference.wav").write_bytes(raw_audio)
            sample_url = f"/media/assets/voices/{vid}/reference.wav"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"音訊解碼失敗: {str(e)}")

    return AssetVoice(
        id=vid,
        name=req.name,
        language="中文 (普通話/國語)",
        gender=req.gender,
        mode=req.mode,
        speed=req.speed,
        position_temperature=req.position_temperature,
        steps=req.steps,
        reference_text=req.reference_text.strip() or None,
        audio_sample_url=sample_url,
        test_audio_url=None,
    )


@router.put("/voices/{voice_id}", response_model=AssetVoice)
def update_voice(voice_id: str, req: UpdateVoiceRequest) -> AssetVoice:
    voices_dir = ASSETS_DIR / "voices"
    voice_dir = voices_dir / voice_id
    if not voice_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定發音人角色")

    yaml_file = voice_dir / "voice.yaml"
    cfg = {}
    if yaml_file.is_file():
        try:
            cfg = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}

    cfg.update({
        "display_name": req.name,
        "gender": req.gender,
        "mode": req.mode,
        "speed": req.speed,
        "position_temperature": req.position_temperature,
        "steps": req.steps,
    })
    yaml_file.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    if req.reference_text.strip():
        (voice_dir / "reference.txt").write_text(req.reference_text.strip() + "\n", encoding="utf-8")

    sample_url = None
    if req.audio_base64:
        try:
            audio_data = req.audio_base64
            if "," in audio_data:
                audio_data = audio_data.split(",", 1)[1]
            raw_audio = base64.b64decode(audio_data)
            temp_raw = voice_dir / "temp_upload_raw"
            temp_raw.write_bytes(raw_audio)
            # 透過 ffmpeg 統一轉為標準 44.1kHz 16-bit 單聲道 WAV 格式
            conv_proc = subprocess.run(
                ["ffmpeg", "-y", "-i", str(temp_raw), "-ar", "44100", "-ac", "1", str(voice_dir / "reference.wav")],
                capture_output=True,
            )
            temp_raw.unlink(missing_ok=True)
            if conv_proc.returncode != 0:
                (voice_dir / "reference.wav").write_bytes(raw_audio)

            ts = int(time.time())
            sample_url = f"/media/assets/voices/{voice_id}/reference.wav?t={ts}"
        except Exception:
            pass
    elif (voice_dir / "reference.wav").is_file():
        rmtime = int((voice_dir / "reference.wav").stat().st_mtime)
        sample_url = f"/media/assets/voices/{voice_id}/reference.wav?t={rmtime}"

    preview_url = None
    if (voice_dir / "preview.wav").is_file():
        pmtime = int((voice_dir / "preview.wav").stat().st_mtime)
        preview_url = f"/media/assets/voices/{voice_id}/preview.wav?t={pmtime}"

    return AssetVoice(
        id=voice_id,
        name=req.name,
        language="中文 (普通話/國語)",
        gender=req.gender,
        mode=req.mode,
        speed=req.speed,
        position_temperature=req.position_temperature,
        steps=req.steps,
        reference_text=req.reference_text.strip() or None,
        audio_sample_url=sample_url,
        test_audio_url=preview_url,
    )


@router.post("/voices/{voice_id}/test")
def test_voice(voice_id: str, req: Optional[TestVoiceRequest] = None) -> dict:
    voices_dir = ASSETS_DIR / "voices"
    voice_dir = voices_dir / voice_id
    if not voice_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定發音人角色")

    yaml_file = voice_dir / "voice.yaml"
    cfg = {}
    if yaml_file.is_file():
        try:
            cfg = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}

    req_obj = req or TestVoiceRequest()
    test_text = (req_obj.text or "歡迎使用智能影視創作系統，這是一段測試發音人音色與位置溫度的語音合成效果。").strip()

    mode = str(req_obj.mode or cfg.get("mode", "clone")).strip().lower()
    speed = float(req_obj.speed if req_obj.speed is not None else cfg.get("speed", 1.0))
    pos_temp = float(req_obj.position_temperature if req_obj.position_temperature is not None else cfg.get("position_temperature", 0.1))
    steps = int(req_obj.steps if req_obj.steps is not None else cfg.get("steps", 32))
    dtype = str(cfg.get("dtype", "fp16")).strip()
    attention = str(cfg.get("attention", "eager")).strip()
    seed = int(cfg.get("seed", 42))
    class_temp = float(cfg.get("class_temperature", 0.0))
    voice_instruct = str(cfg.get("voice_instruct", "女，青年，中音调")).strip()
    instruct = str(req_obj.instruct or cfg.get("instruct", "")).strip()

    comfy_url = os.environ.get("COMFY_URL", "http://comfyui:8188").rstrip("/")

    # 檢查 ComfyUI 連線
    try:
        with urllib.request.urlopen(f"{comfy_url}/system_stats", timeout=5) as resp:
            if resp.status >= 300:
                raise HTTPException(status_code=503, detail="ComfyUI 回應狀態異常")
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"無法連線至 ComfyUI ({comfy_url})。請確認已啟動 ComfyUI 服務 (docker compose --profile comfyui up -d comfyui)",
        )

    ref_audio_name = None
    ref_text_cn = ""
    if mode == "clone":
        ref_wav = voice_dir / "reference.wav"
        ref_txt = voice_dir / "reference.txt"
        if not ref_wav.is_file():
            raise HTTPException(status_code=400, detail="克隆模式缺少 reference.wav 參考音訊，請先上傳")
        if not ref_txt.is_file():
            raise HTTPException(status_code=400, detail="克隆模式缺少 reference.txt 逐字稿")

        ref_text = ref_txt.read_text(encoding="utf-8").strip()
        ref_text_cn = zhconv.convert(ref_text, "zh-cn")
        ref_audio_name = f"{voice_id}_reference.wav"

        with open(ref_wav, "rb") as f:
            up_resp = requests.post(
                f"{comfy_url}/upload/image",
                files={"image": (ref_audio_name, f)},
                data={"overwrite": "true"},
                timeout=15,
            )
        if up_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"上傳參考音訊至 ComfyUI 失敗: {up_resp.text}")

    # 轉為簡體中文送入 OmniVoice
    text_cn = zhconv.convert(test_text, "zh-cn")

    try:
        raw_bytes = _synthesize_sentence(
            text_cn=text_cn,
            voice_instruct=voice_instruct,
            steps=steps,
            speed=speed,
            dtype=dtype,
            attention=attention,
            seed=seed,
            pos_temp=pos_temp,
            class_temp=class_temp,
            comfy_url=comfy_url,
            mode=mode,
            ref_audio_name=ref_audio_name,
            ref_text_cn=ref_text_cn,
            instruct=instruct,
        )

        out_wav = voice_dir / "preview.wav"
        temp_audio = voice_dir / "preview_raw.audio"
        temp_audio.write_bytes(raw_bytes)

        subprocess.run(
            ["ffmpeg", "-y", "-i", str(temp_audio), "-ar", "44100", "-ac", "2", str(out_wav)],
            check=True,
            capture_output=True,
        )
        temp_audio.unlink(missing_ok=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"語音試聽合成失敗: {str(exc)}")

    ts = int(time.time())
    return {
        "success": True,
        "test_audio_url": f"/media/assets/voices/{voice_id}/preview.wav?t={ts}",
        "message": "試聽合成完畢",
    }


@router.delete("/voices/{voice_id}")
def delete_voice(voice_id: str):
    voice_dir = ASSETS_DIR / "voices" / voice_id
    if not voice_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定發音人角色")
    try:
        shutil.rmtree(voice_dir)
        return {"success": True, "deleted_id": voice_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")


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


@router.post("/styles", response_model=AssetStyle)
def create_style(req: CreateStyleRequest) -> AssetStyle:
    sid = _sanitize_id(req.id)
    if not sid:
        raise HTTPException(status_code=400, detail="風格 ID 不得為空")

    presets = load_style_presets()
    if sid in presets:
        raise HTTPException(status_code=400, detail=f"風格 ID 【{sid}】已存在")

    saved_prev = ""
    if req.preview_base64:
        try:
            img_data = req.preview_base64
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            raw_bytes = base64.b64decode(img_data)
            prev_dir = ASSETS_DIR / "styles" / "previews"
            prev_dir.mkdir(parents=True, exist_ok=True)
            target_img = prev_dir / f"{sid}.jpg"
            target_img.write_bytes(raw_bytes)
            saved_prev = f"assets/styles/previews/{sid}.jpg"
        except Exception:
            pass

    save_style_preset(
        style_key=sid,
        name=req.name,
        prefix=req.prefix,
        negative=req.negative or "",
        preview=saved_prev,
        description=req.description,
    )

    prev_url = f"/media/{saved_prev}" if saved_prev else None
    return AssetStyle(
        id=sid,
        name=req.name,
        description=req.description,
        tags=req.tags or ["自訂風格"],
        prefix=req.prefix,
        negative=req.negative or "",
        preview_url=prev_url,
    )


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

    if req.preview_base64:
        try:
            img_data = req.preview_base64
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            raw_bytes = base64.b64decode(img_data)
            prev_dir = ASSETS_DIR / "styles" / "previews"
            prev_dir.mkdir(parents=True, exist_ok=True)
            target_img = prev_dir / f"{style_id}.jpg"
            target_img.write_bytes(raw_bytes)
            current["preview"] = f"assets/styles/previews/{style_id}.jpg"
        except Exception:
            pass

    save_style_preset(
        style_key=style_id,
        name=current["name"],
        prefix=current["prefix"],
        negative=current["negative"],
        preview=current.get("preview", ""),
        description=current["description"],
    )

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


@router.delete("/styles/{style_id}")
def delete_style(style_id: str):
    presets = load_style_presets()
    if style_id not in presets:
        raise HTTPException(status_code=404, detail="找不到指定風格")
    try:
        delete_style_preset(style_id)
        return {"success": True, "deleted_id": style_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")
