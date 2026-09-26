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
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
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
    desc = style["description"] or style["prefix"]
    return f"""ART STYLE LOCK (mandatory — this is the project's selected image style):
- Style name: {style["name"]}
- Visual language: {desc}
- Write faces, bodies, clothing, materials, lighting and atmosphere IN THIS MEDIUM.
- Do NOT add photoreal photography, 35mm film grain, live-action cinematography, or volumetric cinematic lighting unless this style is itself realistic / cinematic.
- Do not contradict the style with a different art movement."""


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
    model: str | None = None,
    # 向下相容參數別名
    tone: str | None = None,
    internet_search: bool | None = None,
) -> str:
    if tone:
        tone_id = tone
    if internet_search is not None:
        search_grounding = internet_search

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

    # 候選模型清單：若使用者指定特定模型，優先排在第一個嘗試
    models_to_try = list(TEXT_MODELS)
    if model and model.strip():
        m = model.strip()
        models_to_try = [m] + [x for x in TEXT_MODELS if x != m]

    errors = []
    for model_name in models_to_try:
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


def extract_story_visual_anchors(
    topic: str,
    script_text: str,
    style_key: str = "",
) -> dict[str, object]:
    """從腳本提煉多名角色外觀（每人獨立）與全片環境光影錨點，並依專案生圖風格書寫。"""
    from aivideo.visual_anchors import compose_subject_anchor, normalize_characters

    style = resolve_style(style_key)
    fallback_appearance = (
        f"The main visual subject representing {topic}, drawn in {style['name']} style, highly detailed, distinct features"
    )
    fallback_env = (
        f"{style['name']} environment, lighting and materials matching this art style, 16:9 widescreen composition"
    )
    excerpt = (script_text or "")[:8000]
    style_lock = style_lock_instructions(style_key)

    try:
        from google import genai
        from google.genai import types

        client_kwargs = get_gemini_client_kwargs()
        client = genai.Client(**client_kwargs)

        prompt = f"""You are a master concept artist and visual continuity director.
Analyze the story topic and script excerpt below.
Extract a CHARACTER BIBLE and one ENVIRONMENT ANCHOR in high-detail ENGLISH.

{style_lock}

Rules:
- List EVERY visually distinct recurring person, creature, or signature machine (up to 8).
- Each character is a separate entry with its own face, body, clothing, colors, and era-accurate details, described as they would appear IN THE LOCKED ART STYLE.
- Do not merge multiple people into one description.
- If the script is about a single protagonist or object, return exactly one character.
- "environment_anchor" is the shared world, architecture, palette, and lighting — not a person — and must match the locked art style (medium, line, color, lighting).

Story Topic: {topic}
Selected image style: {style["name"]}
Script Excerpt:
{excerpt}

OUTPUT FORMAT:
Output JSON with exact keys:
{{
  "characters": [
    {{
      "id": "ascii_slug",
      "name": "Character or entity name",
      "appearance": "English visual description of THIS character only"
    }}
  ],
  "environment_anchor": "English description of world, architecture, lighting..."
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
                        characters = normalize_characters(data.get("characters"))
                        env = str(data.get("environment_anchor", "")).strip()
                        if not characters:
                            sub = str(data.get("subject_anchor", "")).strip() or fallback_appearance
                            characters = normalize_characters(
                                [{"id": "main", "name": "Main Subject", "appearance": sub}]
                            )
                        return {
                            "characters": characters,
                            "subject_anchor": compose_subject_anchor(characters) or fallback_appearance,
                            "environment_anchor": env or fallback_env,
                        }
            except Exception:
                continue
    except Exception:
        pass

    characters = normalize_characters(
        [{"id": "main", "name": "Main Subject", "appearance": fallback_appearance}]
    )
    return {
        "characters": characters,
        "subject_anchor": compose_subject_anchor(characters),
        "environment_anchor": fallback_env,
    }


def batch_generate_english_image_prompts(
    narrations: list[str],
    subject_anchor: str = "",
    environment_anchor: str = "",
    characters: list[dict[str, str]] | None = None,
    style_key: str = "",
) -> list[str]:
    """呼叫 Gemini 將中文旁白台詞批次轉換為專業電影感英文出圖提示詞 (Image Prompts)，並強制融合主體與環境視覺錨點。"""
    if not narrations:
        return []

    from aivideo.visual_anchors import character_bible_for_prompts

    bible = character_bible_for_prompts(characters or [])

    # 嘗試呼叫 Gemini API 批次產生純英文分鏡畫面描述
    try:
        from google import genai
        from google.genai import types

        client_kwargs = get_gemini_client_kwargs()
        client = genai.Client(**client_kwargs)

        tag_pattern = re.compile(r"\[[a-zA-Z0-9_\-]+\]")
        items_text = "\n".join([f"[{i+1}] {tag_pattern.sub('', n).strip()}" for i, n in enumerate(narrations)])
        
        anchor_rules = ""
        if bible or subject_anchor or environment_anchor:
            if bible:
                subject_rule = (
                    "CHARACTER BIBLE (include a character's visual details ONLY when that character actually appears in the scene; never force unused characters into the frame):\n"
                    f"{bible}"
                )
            else:
                subject_rule = f'- MAIN SUBJECT ANCHOR: Whenever the main protagonist/object appears, incorporate these specific physical details: "{subject_anchor}"'
            env_rule = ""
            if environment_anchor:
                env_rule = f'\n- ENVIRONMENT & LIGHTING ANCHOR: Maintain this consistent background atmosphere and cinematic lighting palette: "{environment_anchor}"'
            anchor_rules = f"""
STRICT VISUAL CONTINUITY RULES (Apply to all scenes to maintain consistency):
{subject_rule}{env_rule}
"""

        style = resolve_style(style_key)
        style_lock = style_lock_instructions(style_key)
        prompt = f"""You are a professional storyboard visual artist working strictly in the project's selected art style.
Below is a numbered list of scene narrations from a video.
For each scene, craft an evocative text-to-image prompt strictly in ENGLISH.
{style_lock}
{anchor_rules}
CRITICAL REQUIREMENTS:
1. Every prompt MUST be written completely in ENGLISH.
2. Focus on visual description in the locked art style: subjects, character actions/expressions, lighting and materials that belong to "{style["name"]}", camera angle (wide establishing shot, close-up, low angle), environment, atmosphere, and 16:9 widescreen composition.
3. Do not inject a conflicting medium (for example photoreal live-action if the style is illustration, anime, chibi, or pixel art).
4. NEVER include any dialogue, speech bubbles, quotes, text, subtitles, words, letters, logos, or watermarks.
5. Output EXACTLY a JSON array of strings containing exactly {len(narrations)} prompts in the same order as the input scenes.

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

    # 備援 (Fallback)：若 API 無法連線時，保證提示詞為純英文且帶入錨點與風格
    fallbacks = []
    style = resolve_style(style_key)
    base_sub = subject_anchor if subject_anchor else "the central subject"
    base_env = environment_anchor if environment_anchor else f"{style['name']} environment"
    for _ in narrations:
        fallbacks.append(
            f"{style['name']} wide angle shot featuring {base_sub}, {base_env}, 16:9 widescreen composition"
        )
    return fallbacks


def batch_detect_pip_queries(narrations: list[str]) -> list[str | None]:
    """呼叫 Gemini 批次分析各場景分鏡台詞，判定哪些場景適合搭配真實考據照片 (PiP)，輸出英文檢索詞或 None。"""
    if not narrations:
        return []

    from aivideo.commands.check import _load_dotenv
    _load_dotenv()
    from google import genai
    from google.genai import types

    try:
        client_kwargs = get_gemini_client_kwargs()
        client = genai.Client(**client_kwargs)
    except Exception:
        return [None] * len(narrations)

    scene_items = [{"index": idx + 1, "text": text} for idx, text in enumerate(narrations)]

    prompt = f"""You are an archival visual researcher and documentary editor.
Analyze the following scene narrations for a documentary video.
Identify scenes that mention or describe a SPECIFIC REAL-WORLD entity, historical person, actual scientific instrument/device, spacecraft, telescope, historical event, organism/species, document, or blueprint where displaying a REAL archival photograph (as a Picture-in-Picture card) would strongly enhance documentary credibility.

Scenes:
{json.dumps(scene_items, ensure_ascii=False, indent=2)}

INSTRUCTIONS:
1. For scenes that clearly describe a real-world entity, person, device, spacecraft, organism, or document:
   Provide a concise, precise search query in English suitable for image archives (e.g. "Nancy Grace Roman Space Telescope", "Hubble Space Telescope mirror", "Edward O. Wilson biologist", "Solenopsis invicta fire ant", "ASML EUV lithography machine").
2. For scenes that are purely metaphorical, abstract transitions, or generic narrative where real photo is NOT needed or inappropriate:
   Set query to null.
3. Be selective: only 20%~45% of scenes usually need real archival reference cards to avoid visual clutter.

OUTPUT FORMAT:
Return a JSON array of strings or nulls, with EXACTLY {len(narrations)} items corresponding to the scenes in order:
["Hubble Space Telescope", null, "Nancy Grace Roman", null]
"""

    for model_name in TEXT_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
            if resp.text:
                parsed = json.loads(resp.text)
                if isinstance(parsed, list):
                    result = []
                    for item in parsed:
                        if item and str(item).strip().lower() != "null":
                            result.append(str(item).strip())
                        else:
                            result.append(None)
                    while len(result) < len(narrations):
                        result.append(None)
                    return result[: len(narrations)]
        except Exception:
            continue

    return [None] * len(narrations)


PACING_CONFIGS = {
    "fast": {
        "name": "緊湊快節奏 (Fast)",
        "ideal_range": "1~2 句",
        "max_lines": 3,
        "default_chunk": 2,
        "instruction": "每 1~2 句形成一個獨立分鏡。節奏明快緊湊，適合緊張懸念、名場面衝擊或情緒快速轉折。",
    },
    "balanced": {
        "name": "標準電影感 (Balanced)",
        "ideal_range": "2~4 句",
        "max_lines": 5,
        "default_chunk": 3,
        "instruction": "每 2~4 句形成一個獨立分鏡。依據完整的情節單元、敘事主體轉換或時空環境變化進行自然切鏡，達到最佳觀看舒適度與電影感。",
    },
    "slow": {
        "name": "沉浸長鏡頭 (Slow)",
        "ideal_range": "3~5 句",
        "max_lines": 6,
        "default_chunk": 4,
        "instruction": "每 3~5 句形成一個獨立分鏡。節奏深邃沉穩，著重宏觀世界觀建立、大遠景環境鋪陳與深層氛圍沉浸。",
    },
}


def ai_semantic_chunk_script(
    lines: list[str],
    visual_pacing: str = "balanced",
    topic: str = "",
) -> list[list[str]]:
    """呼叫 Gemini 依據故事台詞的語意、情節單元與視覺場景轉換，自動決定哪幾句話歸為同一個分鏡畫面，
    並參考使用者設定的視覺節奏 (Visual Pacing: fast / balanced / slow)。"""
    if not lines:
        return []

    pacing_key = visual_pacing.lower() if visual_pacing and visual_pacing.lower() in PACING_CONFIGS else "balanced"
    cfg = PACING_CONFIGS[pacing_key]
    max_lines = cfg["max_lines"]
    default_chunk = cfg["default_chunk"]

    # 若總行數過少（例如 <= 2 句），直接作為單幕
    if len(lines) <= 2:
        return [lines]

    try:
        from aivideo.commands.check import _load_dotenv
        _load_dotenv()
        from google import genai
        from google.genai import types

        client_kwargs = get_gemini_client_kwargs()
        client = genai.Client(**client_kwargs)

        numbered_lines = "\n".join([f"[{i + 1}] {line}" for i, line in enumerate(lines)])
        prompt = f"""You are a master Hollywood film director, storyboard artist, and visual editor.
We are converting a spoken video script into cinematic storyboard scenes for image generation.
Analyze the semantic narrative flow, subject transitions, location shifts, and emotional beats below.
Group these script lines into coherent visual scenes according to the target visual pacing.

Topic: {topic or "Documentary Story"}
TARGET PACING: {cfg['name']}
PACING GUIDELINES: {cfg['instruction']}

STRICT RULES:
1. Every scene should ideally cover {cfg['ideal_range']} lines.
2. NEVER assign more than {max_lines} lines to a single scene.
3. Every single line from 1 to {len(lines)} must be included exactly once in chronological, contiguous order without skipping or repetition.
4. Output EXACTLY a JSON array of arrays of integers representing line numbers for each scene.

Script Lines:
{numbered_lines}

OUTPUT FORMAT:
Return ONLY a valid JSON 2D array of integers, like:
[[1, 2], [3, 4, 5], [6, 7]]
"""

        for model_name in TEXT_MODELS:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                if resp.text:
                    parsed = json.loads(resp.text)
                    if isinstance(parsed, list) and parsed:
                        # 驗證與修復結果
                        valid_chunks: list[list[str]] = []
                        last_idx = 0
                        for group in parsed:
                            if not isinstance(group, list):
                                continue
                            group_indices = [int(x) - 1 for x in group if isinstance(x, (int, str)) and str(x).isdigit()]
                            group_indices = [idx for idx in group_indices if 0 <= idx < len(lines)]
                            if not group_indices:
                                continue

                            # 限制單幕上限
                            while len(group_indices) > max_lines:
                                sub = group_indices[:max_lines]
                                valid_chunks.append([lines[i] for i in sub])
                                last_idx = max(last_idx, sub[-1] + 1)
                                group_indices = group_indices[max_lines:]

                            if group_indices:
                                valid_chunks.append([lines[i] for i in group_indices])
                                last_idx = max(last_idx, group_indices[-1] + 1)

                        # 檢查是否有漏掉末尾的句子
                        if last_idx < len(lines):
                            tail = lines[last_idx:]
                            while tail:
                                valid_chunks.append(tail[:max_lines])
                                tail = tail[max_lines:]

                        if valid_chunks:
                            return valid_chunks
            except Exception:
                continue
    except Exception:
        pass

    # 備援 (Fallback)：依據該檔位標準每隔 default_chunk 句進行規則切片
    fallback_chunks: list[list[str]] = []
    for idx in range(0, len(lines), default_chunk):
        fallback_chunks.append(lines[idx : idx + default_chunk])
    return fallback_chunks


def parse_script_lines_to_scenes(
    script_lines_text: str,
    visual_pacing: str = "balanced",
    sentences_per_scene: int | None = None,
    style_key: str = "otomo_katsuhiro",
    subject_anchor: str = "",
    environment_anchor: str = "",
    topic: str = "",
    characters: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """將逐行台詞依據 AI 語意情節與設定的視覺節奏 (Visual Pacing) 自動切分為分鏡場景，
    並為每場分鏡產生英文提示詞與前置分析考據實體 (PiP)。若傳入 sentences_per_scene 則保留向下相容。"""
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

    # 決定分鏡區塊 (Chunks)
    if sentences_per_scene is not None and sentences_per_scene > 0:
        # 向下相容傳統固定句數切分
        chunks: list[list[str]] = []
        chunk_size = max(1, min(5, sentences_per_scene))
        for idx in range(0, len(clean_lines), chunk_size):
            chunks.append(clean_lines[idx : idx + chunk_size])
    else:
        # AI 智能語意切分 (結合視覺節奏)
        chunks = ai_semantic_chunk_script(
            clean_lines,
            visual_pacing=visual_pacing,
            topic=topic,
        )

    narrations = [" ".join(c) for c in chunks]
    english_prompts = batch_generate_english_image_prompts(
        narrations,
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
        characters=characters,
        style_key=style_key,
    )
    pip_queries = batch_detect_pip_queries(narrations)

    scenes: list[dict[str, object]] = []
    for idx, (chunk, narration) in enumerate(zip(chunks, narrations), start=1):
        scene_id = f"{idx:03d}_scene_{idx}"
        img_prompt = (
            english_prompts[idx - 1]
            if idx - 1 < len(english_prompts)
            else "Cinematic wide angle shot, dramatic lighting, 16:9 widescreen composition"
        )
        q = pip_queries[idx - 1] if idx - 1 < len(pip_queries) else None

        scenes.append({
            "id": scene_id,
            "index": idx,
            "title": f"第 {idx} 幕",
            "narration": narration,
            "sentences": chunk,
            "image_prompt": img_prompt,
            "pip_query": q,
        })

    return scenes


def extract_and_create_tone_preset(
    text: str,
    custom_tone_id: str | None = None,
    auto_save: bool = True,
    model: str | None = None,
    custom_title: str | None = None,
) -> dict[str, object]:
    """呼叫 Vertex AI Gemini Flash 模型，深度分析文字檔或參考口白文本，
    提煉出說書人口吻之各項結構特徵，組裝成符合專案規範的 Markdown 並直接寫入 assets/tones/<id>.md。
    """
    _load_dotenv()
    import time
    from google import genai
    from google.genai import types

    client_kwargs = get_gemini_client_kwargs()
    client = genai.Client(**client_kwargs)

    prompt = f"""你是一位資深的影視導演、說書人節目編劇與台詞專家。
請深度分析以下提供的參考口白文本或逐字稿，提煉出專屬的「說書人口吻風格規範與範本」：

【參考文本】
{text[:5000]}

【任務與輸出規範】
請分析該文本的破題節奏、邏輯鋪陳、語言頓挫、情緒起伏與敘事特徵，並以 JSON 格式輸出以下欄位：
1. "id": 英文唯一識別碼（小寫英數字與底線，長度約 8~25 字元，例如 "tech_business_deepdive", "suspense_noir", "investigative_storyteller"）。
2. "title": 具備高度辨識度的說書風格中文名稱（例如："硬核科技商業傳奇風 (杜比模式)", "都市懸疑探案風"）。
3. "tags": 3~6 個精確標籤陣列（例如：["商業", "傳奇", "深度解構", "通俗比喻", "說書"]）。
4. "recommended_voice_instruct": 適合 OmniVoice 語音模型的發音人語氣引導詞（格式範例："女，青年，中音调"、"男，青年，沉穩低音"、"男，中年，渾厚故事感"）。
5. "description": 一句話簡要描述與特徵（約 40~80 字，說明適用題材、片長區間、開場鉤子 Hook、語言比喻與節奏特色）。
6. "sample_narration": 從參考文本中精選或重構出一段約 250~450 字的「精華示範口白」，並嚴格符合專案規範：
   * 標點符號只允許使用全形逗號「，」、問號「？」、感嘆號「！」（絕對嚴禁句號「。」、冒號「：」、頓號「、」、各類引號「」“”‘’、破折號——與括號）。
   * 問號「？」與感嘆號「！」必須極度克制（90%以上使用全形逗號「，」銜接或換行斷句，問號感嘆號每 10~15 句至多出現 1 次）。
   * 自然且克制地嵌入 OmniVoice 官方副語言情緒標籤（如 [surprise-wa]、[surprise-oh]、[question-ei]、[sigh]、[laughter]、[confirmation-en]、[dissatisfaction-hnn] 等，平均每 4~6 句至多 1 個）。
   * 外語名詞、人名、機構名一律標準中譯。
7. "structure_formula": 核心敘事結構與節奏公式（以 Markdown 條列 4~7 個步驟成片法，例如：1. 黃金 8 秒認知反差 Hook、2. 通俗生動降維比喻 Analogy、3. 質疑反詰與預設立場 Tension、4. 乾脆反轉 Reversal、5. 名場面展開、6. 純粹執念昇華致敬等，附帶典型句型引導）。
8. "punctuation_and_emotions": 標點與情緒標籤規範說明（Markdown 條列說明停頓節奏與情緒標籤嵌入時機）。

OUTPUT FORMAT:
Return JSON with the exact keys:
{{
  "id": "...",
  "title": "...",
  "tags": ["..."],
  "recommended_voice_instruct": "...",
  "description": "...",
  "sample_narration": "...",
  "structure_formula": "...",
  "punctuation_and_emotions": "..."
}}
"""

    # 候選模型清單：若使用者指定特定模型，優先排在第一個嘗試
    models_to_try = list(TEXT_MODELS)
    if model and model.strip():
        m = model.strip()
        models_to_try = [m] + [x for x in TEXT_MODELS if x != m]

    data: dict[str, object] = {}
    for model_name in models_to_try:
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
                parsed = json.loads(resp.text)
                if isinstance(parsed, dict) and "title" in parsed:
                    data = parsed
                    break
        except Exception:
            continue

    if not data:
        raise RuntimeError("Vertex AI Gemini Flash 萃取口吻特徵失敗，請確認 API 連線或文字內容。")

    # 處理識別 ID
    def _sanitize(raw: str) -> str:
        c = re.sub(r"[^\w\-]", "_", raw.strip().lower())
        return re.sub(r"_+", "_", c).strip("_")

    tone_id = _sanitize(custom_tone_id) if custom_tone_id else _sanitize(str(data.get("id") or "custom_tone"))
    if not tone_id:
        tone_id = f"tone_{int(time.time())}"

    if custom_title and custom_title.strip():
        title = custom_title.strip()
    else:
        title = str(data.get("title") or "自訂說書人口吻")

    tags_raw = data.get("tags") or ["說書", "自訂"]
    tags = tags_raw if isinstance(tags_raw, list) else [str(tags_raw)]
    tags_str = ", ".join([str(t).strip() for t in tags])

    rec_voice = str(data.get("recommended_voice_instruct") or "女，青年，中音调")
    desc = str(data.get("description") or "由 Vertex AI Gemini Flash 智慧萃取之說書人口吻範本。")
    sample = sanitize_script_punctuation(str(data.get("sample_narration") or "").strip())
    formula = str(data.get("structure_formula") or "").strip()
    punct = str(data.get("punctuation_and_emotions") or "").strip()

    # 組裝成標準 Markdown + YAML Frontmatter
    markdown_content = f"""---
id: {tone_id}
name: {title}
tags: [{tags_str}]
recommended_voice_instruct: "{rec_voice}"
description: {desc}
---

## 核心口白範例文本

> {sample}

## 核心敘事結構與節奏公式
{formula}

## 標點與情緒標籤規範
{punct}
"""

    target_file = None
    if auto_save:
        tones_dir = REPO_ROOT / "assets" / "tones"
        tones_dir.mkdir(parents=True, exist_ok=True)
        target_path = tones_dir / f"{tone_id}.md"
        target_path.write_text(markdown_content.strip() + "\n", encoding="utf-8")
        target_file = f"assets/tones/{tone_id}.md"

    return {
        "id": tone_id,
        "title": title,
        "tags": [str(t).strip() for t in tags],
        "recommended_voice_instruct": rec_voice,
        "summary": desc,
        "content": markdown_content.strip() + "\n",
        "saved": auto_save,
        "file_path": target_file,
    }


def create_job_bundle(
    job_id: str,
    title: str,
    scenes: list[dict[str, object]],
    style_key: str = "otomo_katsuhiro",
    voice_id: str = "female01",
    subject_anchor: str = "",
    environment_anchor: str = "",
    characters: list[dict[str, str]] | None = None,
) -> Path:
    job_dir = REPO_ROOT / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir = job_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    styles = load_style_presets()
    style_cfg = styles.get(style_key, styles.get("otomo_katsuhiro", DEFAULT_STYLE_PRESETS["otomo_katsuhiro"]))

    from aivideo.visual_anchors import compose_subject_anchor, persist_characters_on_anchors

    visual_anchors: dict[str, object] = {
        "subject": subject_anchor,
        "environment": environment_anchor,
        "use_image_reference": True,
    }
    if characters:
        persist_characters_on_anchors(visual_anchors, characters)
        visual_anchors["subject"] = compose_subject_anchor(characters) or subject_anchor

    job_yaml = {
        "id": job_id,
        "title": title,
        "language": "zh-Hant",
        "voice_id": voice_id,
        "visual_anchors": visual_anchors,
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
            "model": os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
            "model_final": os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
            "resolution": "1K",
            "aspect_ratio": "16:9",
            "style": style_key,
        },
        "style_prefix": style_cfg["prefix"],
        "style_negative": style_cfg["negative"],
        "subtitle": {
            "mode": "none",
            "font": "NotoSansTC-Regular.otf",
            "font_size": 48,
        },
        "kenburns": "slow_zoom_in",
    }
    (job_dir / "job.yaml").write_text(yaml.safe_dump(job_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # 寫入 script.md
    script_md_lines = [f"# {title}\n"]
    if characters:
        for ch in characters:
            script_md_lines.append(
                f"> **角色定裝 ({ch.get('name') or ch.get('id')}):** {ch.get('appearance', '')}"
            )
        if environment_anchor:
            script_md_lines.append(f"> **環境錨定 (Environment Anchor):** {environment_anchor}\n")
    elif subject_anchor or environment_anchor:
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
        if s.get("pip_query"):
            q = s["pip_query"]
            from aivideo.auto_pip import infer_pip_mode
            auto_mode = infer_pip_mode(q, str(s.get("narration", "")))
            scfg["pip"] = {
                "enabled": False,  # 標記建議實體，待出圖或一鍵全流程時直接下載啟用
                "image": "pip.png",
                "position": "right-center",
                "mode": auto_mode,
                "scale": 0.24,
                "border": 5,
                "query": q,
            }
        (s_dir / "scene.yaml").write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    return job_dir


def regenerate_job_scene_prompts(
    job_dir: Path,
    subject_anchor: str,
    environment_anchor: str,
    characters: list[dict[str, str]] | None = None,
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

    job_yaml = job_dir / "job.yaml"
    style_key = ""
    if job_yaml.is_file():
        try:
            cfg = yaml.safe_load(job_yaml.read_text(encoding="utf-8")) or {}
            style_key = str((cfg.get("image") or {}).get("style") or cfg.get("style") or "")
            if not characters:
                from aivideo.visual_anchors import ensure_characters
                v = cfg.get("visual_anchors") if isinstance(cfg.get("visual_anchors"), dict) else {}
                characters = ensure_characters(v)
        except Exception:
            style_key = ""

    new_prompts = batch_generate_english_image_prompts(
        narrations,
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
        characters=characters,
        style_key=style_key,
    )

    updated_count = 0
    for idx, (s_yaml_p, scfg) in enumerate(scene_yamls):
        if idx < len(new_prompts):
            scfg["image_prompt"] = new_prompts[idx]
            with open(s_yaml_p, "w", encoding="utf-8") as f:
                yaml.safe_dump(scfg, f, allow_unicode=True, sort_keys=False)
            updated_count += 1

    return updated_count

