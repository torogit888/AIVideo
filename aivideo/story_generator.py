from __future__ import annotations

import json
import os
import re
from pathlib import Path
import yaml

from aivideo.commands.check import _load_dotenv
from aivideo.gemini_image import get_gemini_client_kwargs

REPO_ROOT = Path(__file__).resolve().parents[1]

TEXT_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
)

STYLES_FILE = REPO_ROOT / "assets" / "styles.yaml"

DEFAULT_STYLE_PRESETS = {
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
    # 初始化寫入預設風格
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
    item.update({
        "name": name,
        "prefix": prefix,
        "negative": negative,
    })
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


# 向下相容
STYLE_PRESETS = load_style_presets()


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


def sanitize_script_punctuation(text: str) -> str:
    """自動清理並嚴格規範口白標點符號：
    1. 僅允許使用全形逗號「，」、問號「？」、感嘆號「！」
    2. 嚴禁句號「。」、頓號「、」、冒號「：」、分號「；」，一律替換為全形逗號「，」
    3. 移除各類引號「」『』""''“”‘’、括號、書名號
    4. 壓縮過多重複標點，保留 OmniVoice [tag]
    """
    cleaned_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # 移除引號、書名號、圓括號（保留中括號供 OmniVoice [tag] 使用）
        line = re.sub(r"[「」『』\"'“”‘’《》〈〉（）()]", "", line)
        # 嚴格將句號、頓號、冒號、分號轉為逗號
        line = re.sub(r"[。、：:;；]", "，", line)
        # 破折號、省略號轉為逗號
        line = re.sub(r"[—…]+", "，", line)
        # 壓縮重複標點
        line = re.sub(r"！+", "！", line)
        line = re.sub(r"？+", "？", line)
        line = re.sub(r"，+", "，", line)
        # 去除行首逗號
        line = re.sub(r"^[，,]+", "", line).strip()
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


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
- 標點符號嚴格約束：
  * 全文標點符號只允許使用全形逗號「，」、問號「？」、感嘆號「！」（絕對嚴禁使用句號「。」、冒號「：」、頓號「、」、各類引號「」“”‘’、省略號……、破折號——與括號）。
  * 問號「？」與感嘆號「！」切忌過多：絕大多數句子（90%以上）請使用全形逗號「，」銜接或行末直接換行斷句；問號與感嘆號必須極度克制，僅在真正強烈懸念或極具震撼的情緒高潮時偶爾使用（每 10~15 句至多出現 1 次），保持沉穩洗鍊的頂級說書質感。
- 排版格式：請以「一句一行口白腳本」的樣式輸出，每行獨立一句話（每行約 15~25 字，適合語音逐句合成與字幕顯示）
- 語氣情緒標籤（OmniVoice 專用情緒副語言）：
  請參考 OmniVoice 官方規範，在故事關鍵轉折、懸念或情緒起伏處，自然且克制地在句首或語意處嵌入對應標籤（不用太多，平均每 4~6 句至多出現 1 個，保持沉穩專業，切忌過度頻繁）：
  * [surprise-wa] 或 [surprise-ah]：發現驚人數據、歷史反轉、不可思議的名場面
  * [surprise-oh]：恍然大悟、原來如此
  * [question-ei] 或 [question-yi]：設問質疑、提出懸念思考
  * [question-ah]：強烈反詰、叩問命運
  * [sigh]：歷史沉重、無奈惋惜、艱難困境
  * [laughter]：詼諧自嘲、荒謬幽默、諷刺
  * [confirmation-en]：肯定共識、篤定結論
  * [dissatisfaction-hnn]：質疑抗衡、不滿冷笑

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
                return sanitize_script_punctuation(resp.text.strip())
        except Exception as exc:
            errors.append(f"{model_name}: {exc}")
            continue

    raise RuntimeError("Gemini 腳本生成失敗：\n" + "\n".join(errors))


def extract_story_visual_anchors(topic: str, script_text: str) -> dict[str, str]:
    """呼叫 Gemini 從故事主題與腳本中提煉出『主體視覺特徵錨點 (Subject Anchor)』與『環境基調錨點 (Environment Anchor)』。"""
    try:
        from google import genai
        from google.genai import types

        client_kwargs = get_gemini_client_kwargs()
        client = genai.Client(**client_kwargs)

        prompt = f"""You are a master concept artist and visual continuity director for cinema.
Analyze the story topic and script excerpt below.
Extract and define two essential VISUAL ANCHORS in high-detail ENGLISH to ensure visual consistency across all AI-generated storyboard frames:

1. "subject_anchor": Detailed visual description of the main protagonist, character, or primary entity/machine (e.g. specific physical traits, age, facial features, distinctive clothing, signature colors, or precise mechanical/biological structures).
2. "environment_anchor": Detailed description of the overarching setting, world atmosphere, architecture, and cinematic lighting palette (e.g. time period, dominant colors, lighting style like volumetric rays or chiaroscuro shadows, ambient textures).

Story Topic: {topic}
Script Excerpt:
{script_text[:1800]}

OUTPUT FORMAT:
Output JSON with exact keys:
{{
  "subject_anchor": "English description...",
  "environment_anchor": "English description..."
}}
"""
        for model_name in TEXT_MODELS:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        response_mime_type="application/json",
                    ),
                )
                if resp.text:
                    data = json.loads(resp.text)
                    if isinstance(data, dict):
                        return {
                            "subject_anchor": str(data.get("subject_anchor", "")).strip(),
                            "environment_anchor": str(data.get("environment_anchor", "")).strip(),
                        }
            except Exception:
                continue
    except Exception:
        pass

    return {
        "subject_anchor": f"The main visual subject representing {topic}, highly detailed, distinct features",
        "environment_anchor": "Cinematic atmosphere, dramatic volumetric lighting, detailed textures, 16:9 widescreen composition",
    }


def batch_generate_english_image_prompts(
    narrations: list[str],
    subject_anchor: str = "",
    environment_anchor: str = "",
) -> list[str]:
    """呼叫 Gemini 將中文旁白台詞批次轉換為專業電影感英文出圖提示詞 (Image Prompts)，並強制融合主體與環境視覺錨點。"""
    if not narrations:
        return []

    # 嘗試呼叫 Gemini API 批次產生純英文分鏡畫面描述
    try:
        from google import genai
        from google.genai import types

        client_kwargs = get_gemini_client_kwargs()
        client = genai.Client(**client_kwargs)

        items_text = "\n".join([f"[{i+1}] {re.sub(r'\[[a-zA-Z0-9_\-]+\]', '', n).strip()}" for i, n in enumerate(narrations)])
        
        anchor_rules = ""
        if subject_anchor or environment_anchor:
            anchor_rules = f"""
STRICT VISUAL CONTINUITY RULES (Apply to all scenes to maintain consistency):
- MAIN SUBJECT ANCHOR: Whenever the main protagonist/object appears, incorporate these specific physical details: "{subject_anchor}"
- ENVIRONMENT & LIGHTING ANCHOR: Maintain this consistent background atmosphere and cinematic lighting palette: "{environment_anchor}"
"""

        prompt = f"""You are a master Hollywood film director and professional AI storyboard visual artist.
Below is a numbered list of scene narrations from a video documentary.
For each scene, craft an evocative, professional text-to-image prompt strictly in ENGLISH.
{anchor_rules}
CRITICAL REQUIREMENTS:
1. Every prompt MUST be written completely in ENGLISH.
2. Focus on visual description: subjects, character actions/expressions, cinematic lighting (e.g. volumetric light, chiaroscuro, golden hour, moody shadows), camera angle (e.g. wide angle establishing shot, cinematic close-up, dramatic low angle), environment, atmosphere, and 16:9 widescreen composition.
3. NEVER include any dialogue, speech bubbles, quotes, text, subtitles, words, letters, logos, or watermarks.
4. Output EXACTLY a JSON array of strings containing exactly {len(narrations)} prompts in the same order as the input scenes.

Scenes:
{items_text}
"""
        for model_name in TEXT_MODELS:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.4,
                        response_mime_type="application/json",
                    ),
                )
                if resp.text:
                    parsed = json.loads(resp.text)
                    if isinstance(parsed, list) and len(parsed) == len(narrations):
                        return [str(p).strip() for p in parsed]
            except Exception:
                continue
    except Exception:
        pass

    # 備援 (Fallback)：若 API 無法連線時，保證提示詞為純英文且帶入錨點
    fallbacks = []
    base_sub = subject_anchor if subject_anchor else "the central subject"
    base_env = environment_anchor if environment_anchor else "detailed environment, dramatic lighting"
    for _ in narrations:
        fallbacks.append(
            f"Cinematic wide angle shot featuring {base_sub}, {base_env}, 16:9 widescreen composition, high quality film still"
        )
    return fallbacks


def parse_script_lines_to_scenes(
    script_lines_text: str,
    sentences_per_scene: int = 3,
    style_key: str = "otomo_katsuhiro",
    subject_anchor: str = "",
    environment_anchor: str = "",
) -> list[dict[str, object]]:
    """將逐行台詞按每 2~3 句自動歸納為一個場景分鏡，並為每場分鏡產生英文畫面提示詞 (English Image Prompt)。"""
    # 先行清理並嚴格規範標點符號（頓號、句號、冒號轉逗號，移除引號）
    sanitized_text = sanitize_script_punctuation(script_lines_text)
    raw_lines = [line.strip() for line in sanitized_text.strip().splitlines() if line.strip()]
    # 清理多餘符號
    clean_lines = []
    for l in raw_lines:
        # 去除 markdown 標題符號或序號
        l = re.sub(r"^(#+|\d+[\.\、\s]+)", "", l).strip()
        if l:
            clean_lines.append(l)

    chunks: list[list[str]] = []
    chunk_size = max(1, min(5, sentences_per_scene))

    for idx in range(0, len(clean_lines), chunk_size):
        chunk = clean_lines[idx : idx + chunk_size]
        chunks.append(chunk)

    narrations = [" ".join(c) for c in chunks]
    english_prompts = batch_generate_english_image_prompts(
        narrations,
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
    )

    scenes: list[dict[str, object]] = []
    for idx, (chunk, narration) in enumerate(zip(chunks, narrations), start=1):
        scene_id = f"{idx:03d}_scene_{idx}"
        img_prompt = (
            english_prompts[idx - 1]
            if idx - 1 < len(english_prompts)
            else "Cinematic wide angle shot, dramatic lighting, 16:9 widescreen composition"
        )

        scenes.append({
            "id": scene_id,
            "index": idx,
            "title": f"第 {idx} 幕",
            "narration": narration,
            "sentences": chunk,
            "image_prompt": img_prompt,
        })

    return scenes


def create_job_bundle(
    job_id: str,
    title: str,
    scenes: list[dict[str, object]],
    style_key: str = "otomo_katsuhiro",
    voice_id: str = "female01",
    subject_anchor: str = "",
    environment_anchor: str = "",
) -> Path:
    job_dir = REPO_ROOT / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir = job_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    styles = load_style_presets()
    style_cfg = styles.get(style_key, styles.get("otomo_katsuhiro", DEFAULT_STYLE_PRESETS["otomo_katsuhiro"]))

    job_yaml = {
        "id": job_id,
        "title": title,
        "language": "zh-Hant",
        "voice_id": voice_id,
        "visual_anchors": {
            "subject": subject_anchor,
            "environment": environment_anchor,
        },
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
    if subject_anchor or environment_anchor:
        script_md_lines.append(f"> **主體錨定 (Subject Anchor):** {subject_anchor}")
        script_md_lines.append(f"> **環境錨定 (Environment Anchor):** {environment_anchor}\n")

    for s in scenes:
        script_md_lines.append(f"## {s['index']:03d} {s['title']}")
        script_md_lines.append(f"畫面：{s['image_prompt']}")
        script_md_lines.append(f"旁白：{s['narration']}\n")
    (job_dir / "script.md").write_text("\n".join(script_md_lines), encoding="utf-8")

    # 寫入各場景 scene.yaml
    for s in scenes:
        s_dir = scenes_dir / s["id"]
        s_dir.mkdir(parents=True, exist_ok=True)
        (s_dir / "takes").mkdir(parents=True, exist_ok=True)

        scfg = {
            "id": s["id"],
            "index": s["index"],
            "title": s["title"],
            "narration": s["narration"],
            "image_prompt": s["image_prompt"],
            "image_negative": "",
            "locks": {
                "speech": False,
                "image": False,
            },
            "current": {
                "speech_take": None,
                "image_take": None,
            },
        }
        (s_dir / "scene.yaml").write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    return job_dir


def regenerate_job_scene_prompts(
    job_dir: Path,
    subject_anchor: str,
    environment_anchor: str,
) -> int:
    """依據最新主體與環境錨點，重新為現有 Job 的所有場景批次產生並更新英文提示詞 (Image Prompts)。"""
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return 0

    scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])
    if not scene_folders:
        return 0

    narrations = []
    scene_yamls = []
    for s_dir in scene_folders:
        s_yaml_p = s_dir / "scene.yaml"
        if not s_yaml_p.is_file():
            continue
        try:
            with open(s_yaml_p, "r", encoding="utf-8") as f:
                scfg = yaml.safe_load(f) or {}
            narrations.append(str(scfg.get("narration", "")).strip())
            scene_yamls.append((s_yaml_p, scfg))
        except Exception:
            pass

    new_prompts = batch_generate_english_image_prompts(
        narrations,
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
    )

    updated_count = 0
    for idx, (s_yaml_p, scfg) in enumerate(scene_yamls):
        if idx < len(new_prompts):
            scfg["image_prompt"] = new_prompts[idx]
            with open(s_yaml_p, "w", encoding="utf-8") as f:
                yaml.safe_dump(scfg, f, allow_unicode=True, sort_keys=False)
            updated_count += 1

    return updated_count

