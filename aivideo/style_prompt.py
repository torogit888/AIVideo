"""畫風管理（styles.yaml 讀寫、畫風鎖定指示）與把 style_prefix 接到 image_prompt 前面。"""

from __future__ import annotations

from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
STYLES_FILE = REPO_ROOT / "assets" / "styles.yaml"

DEFAULT_STYLE_PRESETS: dict[str, dict[str, str]] = {
    "otomo_katsuhiro": {
        "name": "大友克洋風格 (Katsuhiro Otomo Style)",
        "description": "經典賽璐珞手繪質感，寫實精準的人物與硬科幻機械結構，電影感寬銀幕分鏡。",
        "prefix": "Katsuhiro Otomo Style",
        "negative": "文字浮水印、現代3D塑料感、低細節模糊、走形手部, text, words, Chinese characters, subtitles, watermark",
        "preview": "assets/styles/previews/otomo_katsuhiro.jpg",
    },
    "japanese_anime": {
        "name": "新海誠日系動漫風格 (Makoto Shinkai Style)",
        "description": "精緻線條，通透唯美光影，色彩飽和，二次元手繪質感，情緒風景。",
        "prefix": "Makoto Shinkai Style",
        "negative": "文字浮水印、寫實暗沉、粗糙雜訊, text, words, Chinese characters, subtitles, watermark",
        "preview": "assets/styles/previews/shinkai_makoto.jpg",
    },
    "studio_ghibli": {
        "name": "吉卜力手繪動畫風格 (Studio Ghibli Style)",
        "description": "宮崎駿手繪賽璐珞質感，溫暖陽光與清澈天空，豐富的自然植被與歐陸奇幻建築。",
        "prefix": "Studio Ghibli Style",
        "negative": "文字浮水印、現代3D渲染、暗沉無光、噪點雜色, text, words, Chinese characters, subtitles, watermark",
        "preview": "assets/styles/previews/studio_ghibli.jpg",
    },
    "kyoto_animation": {
        "name": "京都動畫細膩日常光影風格 (Kyoto Animation Style)",
        "description": "極致精緻的人物刻畫與通透空氣感，溫柔柔和的漫射光與日常生動細節。",
        "prefix": "Kyoto Animation Style",
        "negative": "文字浮水印、粗糙線條、走形畸變、低解析度, text, words, Chinese characters, subtitles, watermark",
        "preview": "assets/styles/previews/kyoto_animation.jpg",
    },
    "ufotable": {
        "name": "ufotable數位光效劇場級動畫風格 (Ufotable Style)",
        "description": "劇場版級華麗光影粒子特效，強烈動態光線，深邃陰影與高度精緻的背景合成。",
        "prefix": "Ufotable Style",
        "negative": "文字浮水印、低對比平淡、粗糙線條、模糊, text, words, Chinese characters, subtitles, watermark",
        "preview": "assets/styles/previews/ufotable.jpg",
    },
}


def load_style_presets() -> dict[str, dict[str, str]]:
    """載入視覺風格預設值。優先從 assets/styles.yaml 載入，若不存在則初始化並存檔。"""
    if STYLES_FILE.is_file():
        try:
            with open(STYLES_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception:
            pass
    save_all_style_presets(DEFAULT_STYLE_PRESETS)
    return dict(DEFAULT_STYLE_PRESETS)


def save_all_style_presets(styles: dict[str, dict[str, str]]) -> None:
    STYLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STYLES_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(styles, f, allow_unicode=True, sort_keys=False)


def save_style_preset(
    style_key: str,
    name: str,
    prefix: str,
    negative: str,
    preview: str = "",
    description: str = "",
) -> None:
    styles = load_style_presets()
    item = styles.get(style_key, {})
    item.update(
        {
            "name": name,
            "prefix": prefix,
            "negative": negative,
        }
    )
    if preview:
        item["preview"] = preview
    elif "preview" not in item:
        item["preview"] = ""
    if description:
        item["description"] = description
    elif "description" not in item:
        item["description"] = ""
    styles[style_key] = item
    save_all_style_presets(styles)


def delete_style_preset(style_key: str) -> bool:
    styles = load_style_presets()
    if style_key in styles:
        prev_path = styles[style_key].get("preview")
        if prev_path:
            p_file = REPO_ROOT / prev_path
            if p_file.is_file() and "assets/styles/previews" in str(p_file).replace("\\", "/"):
                try:
                    p_file.unlink()
                except Exception:
                    pass
        del styles[style_key]
        save_all_style_presets(styles)
        return True
    return False


def resolve_style(style_key: str | None = None) -> dict[str, str]:
    """取得專案生圖風格的名稱、prefix 與說明，供分析與分鏡 prompt 鎖定畫風。"""
    styles = load_style_presets()
    key = (style_key or "").strip()
    info = styles.get(key) if key else None
    if not isinstance(info, dict) or not info:
        info = styles.get("otomo_katsuhiro") or next(iter(styles.values()), {}) or {}
        key = key or "otomo_katsuhiro"
    return {
        "key": key,
        "name": str(info.get("name") or key or "").strip(),
        "prefix": str(info.get("prefix") or "").strip(),
        "description": str(info.get("description") or "").strip(),
        "negative": str(info.get("negative") or "").strip(),
    }


def style_lock_instructions(style_key: str | None = None) -> str:
    style = resolve_style(style_key)
    prefix = style["prefix"]
    desc = style["description"]
    visual_spec = f"{prefix} ({desc})" if (prefix and desc) else (prefix or desc or style["name"])
    return f"""ART STYLE LOCK (mandatory — this is the project's selected image style):
- Style ID: {style["key"]} ({style["name"]})
- English Style Keywords: {prefix or style["name"]}
- Visual Language: {visual_spec}
- Write faces, bodies, clothing, materials, lighting and atmosphere STRICTLY IN THIS MEDIUM in 100% ENGLISH (NEVER include Chinese characters or Chinese style names inside `image_prompt`).
- Do NOT add photoreal photography, 35mm film grain, live-action cinematography, or dark "dramatic lighting" unless this style is itself realistic / cinematic.
- Do not contradict the style with a different art movement."""


def is_generic_fallback_prompt(prompt: str | None) -> bool:
    """偵測分鏡 image_prompt 是否為空或落入了無劇情內容的保底罐頭句。"""
    text = (prompt or "").strip()
    if not text:
        return True
    lower = text.lower()
    if lower.endswith("cinematic wide angle shot, dramatic lighting, 16:9 widescreen composition"):
        prefix_part = lower[: -len("cinematic wide angle shot, dramatic lighting, 16:9 widescreen composition")].strip(" ,，")
        # 若扣掉罐頭結尾後只剩風格名稱或少於 4 個英文單詞，代表完全沒有該幕劇情描述
        en_words = [w for w in prefix_part.replace(",", " ").split() if w.isascii() and w.isalpha()]
        if len(en_words) <= 5:
            return True
    return False


def compose_styled_prompt(style_prefix: str, prompt: str) -> str:
    prefix = (style_prefix or "").strip().strip("，, ")
    body = (prompt or "").strip()
    if not prefix:
        return body
    if not body:
        return prefix
    if body.startswith(prefix):
        return body
    head = body[: max(len(prefix) + 12, 96)]
    if prefix in head:
        return body
    # 若 prefix 為多行長句，檢查首段前 40 字元是否已出現在 body 開頭，避免重複疊加兩次畫風前綴
    first_line_head = prefix.splitlines()[0].strip()[:40]
    if len(first_line_head) >= 16 and first_line_head.lower() in body[:80].lower():
        return body
    # 只要 style_prefix 本身是英文，一律使用英文逗號 ", " 拼接，避免全形逗號影響影像模型
    prefix_has_cjk = any("\u4e00" <= c <= "\u9fff" for c in prefix)
    body_has_cjk = any("\u4e00" <= c <= "\u9fff" for c in body)
    sep = "，" if (prefix_has_cjk and body_has_cjk) else ", "
    return f"{prefix}{sep}{body}".strip("，, ")
