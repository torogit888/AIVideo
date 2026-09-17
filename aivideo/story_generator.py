from __future__ import annotations

import os
import re
from pathlib import Path
import yaml

from aivideo.commands.check import _load_dotenv
from aivideo.gemini_image import get_gemini_client_kwargs

REPO_ROOT = Path(__file__).resolve().parents[1]

TEXT_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.1-flash",
    "gemini-3-flash",
)

STYLE_PRESETS = {
    "otomo_katsuhiro": {
        "name": "大友克洋漫畫與動畫電影風格 (Katsuhiro Otomo)",
        "prefix": "大友克洋漫畫與動畫電影風格，80年代經典賽璐珞手繪質感，寫實精準的人物與硬科幻機械結構，極高密度的管線與金屬細節，電影感寬銀幕分鏡，自然手繪光影與陰影線條，16:9 橫式構圖",
        "negative": "文字浮水印、現代3D塑料感、低細節模糊、走形手部",
    },
    "cinematic_realistic": {
        "name": "電影寫實風格 (Cinematic Realistic)",
        "prefix": "電影感靜幀，35mm鏡頭，膠片顆粒，自然電影光影，高動態範圍，精細細節，16:9 橫式構圖",
        "negative": "文字浮水印、過曝、變形、塑料感",
    },
    "japanese_anime": {
        "name": "新海誠日系動漫風格 (Japanese Anime)",
        "prefix": "新海誠日系動漫風格，精緻線條，通透唯美光影，色彩飽和，二次元手繪質感，16:9 橫式構圖",
        "negative": "文字浮水印、寫實暗沉、粗糙雜訊",
    },
    "european_fairytale": {
        "name": "歐式古典童話繪本風格 (European Fairytale)",
        "prefix": "歐式古典童話繪本插畫，溫暖水彩厚塗，柔和邊緣，奇幻童趣，精緻筆觸，16:9 橫式構圖",
        "negative": "文字浮水印、照片寫實、現代冰冷科技感",
    },
    "retro_scifi": {
        "name": "70年代復古科幻太空風格 (Retro Sci-Fi)",
        "prefix": "70年代復古科幻太空插畫，NASA復古海報風格，顆粒質質感，深邃星空，機械構造，16:9 橫式構圖",
        "negative": "文字浮水印、數碼平滑、雜亂畸形",
    },
}


def load_tone_sample(tone_id: str) -> str:
    tones_dir = REPO_ROOT / "assets" / "tones"
    tone_file = tones_dir / f"{tone_id}.md"
    if not tone_file.is_file():
        # 嘗試直接查找
        matches = list(tones_dir.glob(f"*{tone_id}*.md"))
        if matches:
            tone_file = matches[0]
        else:
            return ""
    return tone_file.read_text(encoding="utf-8")


def generate_story_script(
    topic: str,
    tone_id: str = "tech_business_deepdive",
    word_count: int = 2000,
    search_grounding: bool = True,
) -> str:
    _load_dotenv()
    from google import genai
    from google.genai import types

    client_kwargs = get_gemini_client_kwargs()
    client = genai.Client(**client_kwargs)

    tone_sample = load_tone_sample(tone_id)

    prompt = f"""你是一位擁有數百萬訂閱的 YouTube 頂級說書人與知識專欄作家。
請根據以下標準指令與約束，為我撰寫一篇深度故事腳本：

【主題】
介紹：{topic}

【基本需求】
- 字數規模：約 {word_count} 字的中文深度故事（適合約 8~12 分鐘的 YouTube 專題影片）
- 資料深度：盡可能挖掘該主題的真實歷史、人物細節、爭議轉折點、技術與商業本質、傳奇名場面
- 語言規範：盡量不要有英文，外國人名、機構名、專業術語一律標準中文通譯（避免中文語音模型拼讀字母破音）
- 標點符號約束：全文標點符號只允許使用「，」、「？」、「！」（絕對禁止使用冒號、各類引號、句號、省略號）
- 排版格式：請以「一句一行口白腳本」的樣式輸出，每行獨立一句話（每行約 15~25 字，適合語音逐句合成與字幕顯示）

【口吻風格參照】
{tone_sample if tone_sample else "請使用極具感染力、短句頓挫、反詰質疑後驚喜反轉的說書口吻。"}

請直接輸出逐行口白內容，不要輸出開頭客套話："""

    config_kwargs: dict[str, object] = {
        "temperature": 0.75,
    }
    if search_grounding:
        config_kwargs["tools"] = [{"google_search": {}}]

    config = types.GenerateContentConfig(**config_kwargs)

    errors = []
    for model_name in TEXT_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            if resp.text:
                return resp.text.strip()
        except Exception as exc:
            errors.append(f"{model_name}: {exc}")
            continue

    raise RuntimeError("Gemini 腳本生成失敗：\n" + "\n".join(errors))


def parse_script_lines_to_scenes(
    script_lines_text: str,
    sentences_per_scene: int = 3,
    style_key: str = "otomo_katsuhiro",
) -> list[dict[str, object]]:
    """將逐行台詞按每 2~3 句自動歸納為一個場景分鏡。"""
    raw_lines = [line.strip() for line in script_lines_text.strip().splitlines() if line.strip()]
    # 清理多餘符號
    clean_lines = []
    for l in raw_lines:
        # 去除 markdown 標題符號或序號
        l = re.sub(r"^(#+|\d+[\.\、\s]+)", "", l).strip()
        if l:
            clean_lines.append(l)

    scenes: list[dict[str, object]] = []
    chunk_size = max(1, min(5, sentences_per_scene))

    for idx in range(0, len(clean_lines), chunk_size):
        chunk = clean_lines[idx : idx + chunk_size]
        scene_idx = (idx // chunk_size) + 1
        scene_id = f"{scene_idx:03d}_scene_{scene_idx}"
        narration = " ".join(chunk)

        # 根據台詞生成畫面提示詞關鍵字
        summary_prompt = f"{chunk[0][:30]}，電影感寬銀幕構圖，細節豐富"

        scenes.append({
            "id": scene_id,
            "index": scene_idx,
            "title": f"第 {scene_idx} 幕",
            "narration": narration,
            "sentences": chunk,
            "image_prompt": summary_prompt,
        })

    return scenes


def create_job_bundle(
    job_id: str,
    title: str,
    scenes: list[dict[str, object]],
    style_key: str = "otomo_katsuhiro",
    voice_id: str = "female01",
) -> Path:
    job_dir = REPO_ROOT / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir = job_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    style_cfg = STYLE_PRESETS.get(style_key, STYLE_PRESETS["otomo_katsuhiro"])

    job_yaml = {
        "id": job_id,
        "title": title,
        "language": "zh-Hant",
        "voice_id": voice_id,
        "frame": {
            "aspect": "16:9",
            "gen_width": 1920,
            "gen_height": 1080,
            "deliver_width": 1920,
            "deliver_height": 1080,
            "fps": 30,
        },
        "image": {
            "backend": "gemini",
            "model": "gemini-3.1-flash-image",
            "model_final": "gemini-3-pro-image",
            "resolution": "1K",
            "aspect_ratio": "16:9",
            "style": style_key,
        },
        "style_prefix": style_cfg["prefix"],
        "style_negative": style_cfg["negative"],
        "subtitle": {
            "mode": "hard",
            "font": "NotoSansTC-Regular.otf",
            "font_size": 48,
        },
        "kenburns": "slow_zoom_in",
    }
    (job_dir / "job.yaml").write_text(yaml.safe_dump(job_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # 寫入 script.md
    script_md_lines = [f"# {title}\n"]
    for s in scenes:
        script_md_lines.append(f"## {s['index']:03d} {s['title']}")
        script_md_lines.append(f"畫面：{s['image_prompt']}")
        script_md_lines.append(f"旁白：{s['narration']}\n")
    (job_dir / "script.md").write_text("\n".join(script_md_lines), encoding="utf-8")

    # 寫入各場景 scene.yaml
    for s in scenes:
        s_folder = scenes_dir / s["id"]
        s_folder.mkdir(parents=True, exist_ok=True)
        s_yaml = {
            "id": s["id"],
            "index": s["index"],
            "title": s["title"],
            "narration": s["narration"],
            "image_prompt": s["image_prompt"],
            "image_negative": "",
            "locks": {"speech": False, "image": False},
            "current": {"speech_take": None, "image_take": None},
        }
        (s_folder / "scene.yaml").write_text(yaml.safe_dump(s_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8")

    return job_dir
