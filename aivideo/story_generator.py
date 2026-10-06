from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
import yaml

from aivideo.commands.check import _load_dotenv
from aivideo.gemini_image import get_gemini_client_kwargs
from aivideo.naming import DEFAULT_VOICE_ID, scene_folder_id, scene_title_from_narration
from aivideo.spoken import OMNIVOICE_TAG_RE as _OMNIVOICE_TAG_RE

REPO_ROOT = Path(__file__).resolve().parents[1]

TEXT_MODELS = (
    "gemini-3.8-flash",
    "grok-4.7",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-flash-latest",
)


def resolve_text_model_name(model_name: str | None) -> str:
    """將使用者或前端傳入的模型名稱映射為 Vertex AI 支援的真實名稱（如 xai/grok-4.7）。"""
    m = (model_name or "").strip()
    if not m:
        return "gemini-3.8-flash"
    if m.lower() in {"grok-4.7", "grok4.7", "grok", "xai-grok-4.7"}:
        return "xai/grok-4.7"
    return m


def get_candidate_text_models(preferred_model: str | None = None) -> list[str]:
    """取得依優先權排列的候選文本模型清單，指定模型排最前，並自動正規化名稱。"""
    resolved_preferred = resolve_text_model_name(preferred_model) if preferred_model and preferred_model.strip() else None
    candidates: list[str] = []
    if resolved_preferred:
        candidates.append(resolved_preferred)
    for m in TEXT_MODELS:
        resolved = resolve_text_model_name(m)
        if resolved not in candidates:
            candidates.append(resolved)
    return candidates

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


_SCENE_HEADER_RE = re.compile(
    r"^\s*([【\[\(（#*]*\s*第[一二三四五六七八九十\d]+[幕章節集場次]|幕[一二三四五六七八九十\d]+[：:]|Act\s*\d+|Chapter\s*\d+|Scene\s*\d+)",
    re.IGNORECASE,
)
_OUTLINE_LABEL_RE = re.compile(
    r"(幕次標題|核心矛盾衝突|關鍵真實歷史|此幕要帶給觀眾|情節大綱|關鍵看點)"
)
_META_DIRECTION_RE = re.compile(
    r"(讓觀眾(思考|理解|迫切|知道)|帶給觀眾|要帶給觀眾|"
    r"我們深入探討了|這也讓我們探討|讓我們探討|"
    r"鋪陳出.{0,24}(潛力|艱難|背景)|"
    r"展現了.{0,24}(遠見|手腕|能力))"
)
_VISUAL_DIRECTION_RE = re.compile(r"^(畫面|分鏡|鏡頭|場景提示)\s*[：:]")
_NARRATION_PREFIX_RE = re.compile(r"^(旁白|解說|口白)\s*[：:]\s*")
_OUTLINE_TITLE_FIELD_RE = re.compile(
    r"(?:幕次標題[^\n：:]*|核心矛盾衝突)[：:]\s*(.+)"
)
_OUTLINE_MOOD_FIELD_RE = re.compile(r"此幕要帶給觀眾[^\n：:]*[：:]\s*(.+)")


def _spoken_text_for_compare(line: str) -> str:
    text = _OMNIVOICE_TAG_RE.sub("", line or "")
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)


def _strip_md_phrase(text: str) -> str:
    return re.sub(r"\*+", "", text or "").strip()


def extract_outline_leak_phrases(notes: str | None) -> list[str]:
    """從大綱場記抽出不該被唸出口白的標題與短情緒標註（不含整段筆記正文）。"""
    if not notes:
        return []
    phrases: list[str] = []
    for raw_line in notes.splitlines():
        line = _strip_md_phrase(raw_line).lstrip("-# ").strip()
        if not line:
            continue
        title_match = _OUTLINE_TITLE_FIELD_RE.search(line)
        if title_match:
            phrases.append(_strip_md_phrase(title_match.group(1)))
        mood_match = _OUTLINE_MOOD_FIELD_RE.search(line)
        if mood_match:
            rest = _strip_md_phrase(mood_match.group(1))
            first_clause = re.split(r"[，。？！、；：:]", rest, maxsplit=1)[0].strip()
            if first_clause:
                phrases.append(first_clause)
            # 只收短場記，避免長段情緒說明把正常口白子句一起濾掉
            if rest and len(_spoken_text_for_compare(rest)) <= 24:
                phrases.append(rest)
    return phrases


def _line_copies_outline_note(line: str, phrases: list[str]) -> bool:
    spoken = _spoken_text_for_compare(line)
    if len(spoken) < 6 or not phrases:
        return False
    for phrase in phrases:
        target = _spoken_text_for_compare(phrase)
        if len(target) < 6:
            continue
        if spoken == target:
            return True
        # 短標題／情緒頭：口白幾乎就是那句場記，或只多了「這是／這一幕」之類前綴
        if target in spoken and len(spoken) <= len(target) + 8:
            return True
        if spoken in target and len(spoken) <= 18 and len(target) <= 24:
            return True
        if len(spoken) >= 10 and len(target) >= 10:
            if SequenceMatcher(None, spoken, target).ratio() >= 0.82:
                return True
    return False


def is_non_spoken_script_line(line: str, outline_phrases: list[str] | None = None) -> bool:
    """判斷一行是否為場記、幕次標題、情緒標註或後設說明，而非可朗讀口白。"""
    raw = (line or "").strip()
    if not raw:
        return True
    if _SCENE_HEADER_RE.match(raw) or _VISUAL_DIRECTION_RE.match(raw):
        return True
    if _OUTLINE_LABEL_RE.search(raw) or _META_DIRECTION_RE.search(raw):
        return True
    spoken = _spoken_text_for_compare(raw)
    if 4 <= len(spoken) <= 16 and not re.search(r"[你我他她您咱這那是否嗎呢吧]", spoken):
        if re.search(r"(感|好奇心|張力|震撼|無奈|荒誕|荒謬|情緒)", spoken):
            return True
    if outline_phrases and _line_copies_outline_note(raw, outline_phrases):
        return True
    return False


def extract_tone_spoken_sample(tone_md: str) -> str:
    """只取出語氣範本中的口白範例，避免結構公式被模型當台詞輸出。"""
    if not tone_md:
        return ""
    match = re.search(
        r"##\s*(核心口白範例[^\n]*|參考口白[^\n]*)\n+(.*?)(?=\n##\s+|\Z)",
        tone_md,
        re.S,
    )
    if match:
        return match.group(2).strip()
    return tone_md.strip()


def split_long_narration_line(line: str, max_chars: int = 30) -> list[str]:
    """若單行口白包含多個逗號子句且過長，在適當的逗號停頓處拆分為多行獨立口白（每行約 15~25 字）。"""
    line = line.strip()
    line = re.sub(r"^[，,]+", "", line).strip()
    if not line:
        return []
    if len(line) <= max_chars or "，" not in line:
        return [line]

    parts = [p.strip() for p in line.split("，") if p.strip()]
    if len(parts) <= 1:
        return [line]

    result = []
    current_chunk = ""
    for part in parts:
        if not current_chunk:
            current_chunk = part
        elif len(current_chunk) + len(part) + 1 <= max_chars:
            current_chunk += "，" + part
        else:
            result.append(current_chunk + "，")
            current_chunk = part
    if current_chunk:
        result.append(current_chunk)
    return result


def sanitize_script_punctuation(text: str, outline_notes: str | None = None) -> str:
    """自動清理並嚴格規範口白標點符號：
    1. 僅允許使用全形逗號「，」、問號「？」、感嘆號「！」
    2. 句號「。」、分號「；」自動切分為獨立換行
    3. 頓號「、」、冒號「：」一律替換為全形逗號「，」
    4. 移除各類引號「」『』""''“”‘’、括號、書名號
    5. 若單行過長（>30字）且包含逗號，自動在停頓處智慧分行，維持「一句一行」
    6. 壓縮過多重複標點，保留 OmniVoice [tag]
    7. 過濾章節／幕次標題、畫面提示、大綱場記、情緒標註與「讓觀眾思考」等後設說明，確保純口白
    """
    # 句號與分號視為句子結束，優先轉換為斷行
    text = re.sub(r"[。；]", "\n", text)
    outline_phrases = extract_outline_leak_phrases(outline_notes)

    cleaned_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if is_non_spoken_script_line(line, outline_phrases):
            continue
        line = _NARRATION_PREFIX_RE.sub("", line).strip()
        # 移除引號、書名號、圓括號（保留中括號供 OmniVoice [tag] 使用）
        line = re.sub(r"[「」『』\"'“”‘’《》〈〉（）()]", "", line)
        # 頓號、冒號轉為逗號
        line = re.sub(r"[、：:]", "，", line)
        # 破折號、省略號轉為逗號
        line = re.sub(r"[—…]+", "，", line)
        # 壓縮重複標點
        line = re.sub(r"！+", "！", line)
        line = re.sub(r"？+", "？", line)
        line = re.sub(r"，+", "，", line)
        # 去除行首逗號
        line = re.sub(r"^[，,]+", "", line).strip()
        if not line or is_non_spoken_script_line(line, outline_phrases):
            continue

        # 過長單行智慧切分，保證一行一句（約 15~25 字）
        sub_lines = split_long_narration_line(line, max_chars=30)
        for sl in sub_lines:
            sl = re.sub(r"^[，,]+", "", sl).strip()
            if sl and not is_non_spoken_script_line(sl, outline_phrases):
                cleaned_lines.append(sl)

    return "\n".join(cleaned_lines)


def generate_story_outline(
    topic: str,
    tone_id: str = "michelin_curious",
    model: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """由 AI 聯網檢索並規劃長篇深度故事的 6~8 個核心情節大綱與關鍵看點，可依據使用者自訂的 Prompt/靈感深化。"""
    _load_dotenv()
    from google import genai
    from google.genai import types

    tone_sample = load_tone_sample(tone_id)

    user_prompt_section = ""
    if user_prompt and user_prompt.strip():
        user_prompt_section = f"""
【使用者核心指示與自訂 Prompt 要求（重要基石）】
{user_prompt.strip()}
請務必緊扣並融入使用者上述指定的靈感看點、情節要求或人物視角，以此為基石規劃展開！
"""

    prompt = f"""你是一位頂級專題紀錄片與故事腳本總策劃。
請針對以下主題進行深度資料檢索，規劃一套結構嚴密、高潮迭起、長達 12~15 分鐘（目標約 4000 字）的「6～8 幕核心情節大綱與關鍵看點」：

【主題】
{topic}
{user_prompt_section}
【口吻風格與敘事公式參照（關鍵）】
{tone_sample if tone_sample else "請使用極具感染力、短句頓挫、反詰質疑後驚喜反轉的敘事風格。"}
請嚴格依據上述風格範本中的「核心敘事結構與節奏公式」（如反差鉤子 Hook、困境鋪陳、核心機制拆解、矛盾交鋒、反噬或警示、昇華反思等）來構建各幕次的情節走向！
【人設禁令】：嚴禁自稱「說書人」、「小編」等任何預設稱謂，開場與視角必須 100% 依循上方風格範本的人設與口吻。

【大綱規劃原則】
1. 請條列 6～8 個獨立幕次，每幕包含：
   - 幕次標題與核心矛盾衝突
   - 關鍵真實歷史/技術細節、數據對抗或人物名場面
   - 此幕要帶給觀眾的懸念或情緒高潮
2. 避免空泛概述，請給出具體人物姓名、時間點、關鍵事件與技術關鍵詞
3. 排版請簡潔有力，條列式輸出（例如「第一幕：...」、「第二幕：...」）
4. 「幕次標題」與「此幕要帶給觀眾的懸念或情緒高潮」是給下一階段編劇看的場記，不是口白。請用內部筆記語氣書寫，後續腳本必須改寫成聽眾聽得懂的台詞，不得把這些欄位原句唸出來。

請直接輸出繁體中文的大綱內容："""

    config = types.GenerateContentConfig(
        temperature=0.7,
        tools=[{"google_search": {}}],
    )

    models_to_try = get_candidate_text_models(model)
    errors = []
    for model_name in models_to_try:
        try:
            client = genai.Client(**get_gemini_client_kwargs(model=model_name))
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

    raise RuntimeError("AI 大綱規劃失敗：\n" + "\n".join(errors))


def generate_story_script(
    topic: str,
    tone_id: str = "michelin_curious",
    word_count: int = 2000,
    search_grounding: bool = True,
    model: str | None = None,
    notes: str | None = None,
    user_prompt: str | None = None,
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

    tone_sample = extract_tone_spoken_sample(load_tone_sample(tone_id))

    user_prompt_section = ""
    if user_prompt and user_prompt.strip():
        user_prompt_section = f"""
【使用者核心指示與指定 Prompt（重要客製化要求）】
{user_prompt.strip()}
請務必將使用者上述指定的劇情看點、人物關係或視角要求深度融入故事各幕中！
"""

    notes_section = ""
    if notes and notes.strip():
        notes_section = f"""
【故事核心大綱與關鍵看點（僅供內部情節骨架，禁止照抄欄位文字）】
{notes.strip()}
請嚴格依據上述大綱架構逐幕深入鋪陳，每幕展開足夠的台詞與名場面細節，切忌一筆帶過！
大綱裡的「幕次標題」「核心矛盾衝突」「此幕要帶給觀眾的懸念或情緒高潮」是給編劇看的場記。
必須改寫成聽眾聽得懂的說書口白，嚴禁把標題或情緒標註原句唸出來。
"""

    # 依目標字數動態量化行數與每幕配額（中文口白每行約 18~22 字，以平均 20 字估算）
    target_total_lines = max(20, round(word_count / 20))
    min_words = int(word_count * 0.9)
    max_words = int(word_count * 1.1)
    # 預期 6~8 幕，以 6 幕估算每幕平均句數
    target_lines_per_scene = max(5, round(target_total_lines / 6))

    prompt = f"""你是一位頂級深度故事與影片腳本創作者。
請完全依照指定的主題、使用者要求與口吻風格範本，為我撰寫一篇深度故事腳本：

【主題】
介紹：{topic}
{user_prompt_section}
{notes_section}
【基本需求與字數規模配額（極重要）】
- 字數規模：目標嚴格控制在約 {word_count} 字左右（容許區間：{min_words} ～ {max_words} 字，絕不可草率縮水亦不可無節制灌水）
- 總口白行數要求：全文必須輸出約 {target_total_lines} 行獨立口白（一句一行）
- 篇幅與幕次分配（關鍵）：
  * 故事請涵蓋 6～8 個完整轉折幕次（起承轉合、危機爆發、生死對決、技術/商業本質拆解、高潮反轉與歷史昇華）。
  * 每一幕必須包含充足飽滿的口白量（平均每幕請分配約 {target_lines_per_scene} 行台詞），情節層層推進，嚴格禁止浮光掠影般草草收尾。
- 人設與禁令（極為關鍵）：
  * 【絕對嚴格禁止自稱「說書人」、「小編」或出現任何「我是說書人」的語句】！
  * 開場與全篇人設視角必須 100% 嚴格依照下方【口吻風格參照】的範本與語調發聲（例如若風格範本是以提問或直接點題開場，請直接切入，切勿加入多餘自稱）。
- 絕對最高禁令（純口白保證）：
  * 全文 100% 必須為直接說出的純台詞口白！每一行都必須是說書人會對聽眾親口講出的句子。
  * 【絕對嚴格禁止】輸出任何章節標題、幕次名稱、場景標號或過渡前綴（嚴格禁止出現「第一幕：...」、「第二幕」、「第1幕」、「【第一幕】」、「幕次一」、「引言」、「結語」等任何結構標記）。
  * 大綱場記一律禁止唸出：幕次標題、核心矛盾衝突、「此幕要帶給觀眾的懸念或情緒高潮」及其內容（例如「強烈的荒謬感與好奇心」這類情緒標註）。
  * 嚴禁輸出導演筆記、畫面說明、結構標籤，以及「讓觀眾思考／讓觀眾理解／帶給觀眾／鋪陳出／展現了…手腕」等對製作人員說話的後設句子。
  * 聽眾只會聽到你嘴巴講出來的故事台詞，因此嚴禁出現任何給讀者看的章節小標題或場記！
- 資料深度：盡可能挖掘該主題的真實歷史、人物細節、爭議轉折點、技術與商業本質、傳奇名場面
- 語言規範：盡量不要有英文，外國人名、機構名、專業術語一律標準中文通譯（避免中文語音模型拼讀字母破音）
- 標點符號嚴格約束：
  * 全文標點符號只允許使用全形逗號「，」、問號「？」、感嘆號「！」（絕對嚴禁使用句號「。」、冒號「：」、頓號「、」、各類引號「」“”‘’、省略號……、破折號——與括號）。
  * 問號「？」與感嘆號「！」切忌過多：絕大多數句子（90%以上）請使用全形逗號「，」銜接或行末直接換行斷句；問號與感嘆號必須極度克制，僅在真正強烈懸念或極具震撼的情緒高潮時偶爾使用（每 10~15 句至多出現 1 次），保持沉穩洗鍊的頂級質感。
- 排版格式（絕對死命令：一句一行，嚴禁輸出大段落！）：
  * 必須是「一句一行獨立口白腳本」，每行只講一句話（每行嚴格限制在 15~25 字左右，說完一句必須立即按下 Enter 換行）！
  * 絕對嚴格禁止把多個分句用逗號串聯成一長段，每一行都必須是獨立簡潔的一句話！
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

【口吻風格參照（只模仿語氣與句式，禁止輸出結構標題或節奏公式名稱）】
{tone_sample if tone_sample else "請使用極具感染力、短句頓挫、反詰質疑後驚喜反轉的敘事風格。"}

請直接輸出逐行口白內容，不要輸出開頭客套話，切勿自稱說書人："""

    config_kwargs: dict[str, object] = {
        "temperature": 0.75,
    }
    if search_grounding:
        config_kwargs["tools"] = [{"google_search": {}}]

    config = types.GenerateContentConfig(**config_kwargs)

    # 候選模型清單：若使用者指定特定模型，優先排在第一個嘗試
    models_to_try = get_candidate_text_models(model)

    errors = []
    for model_name in models_to_try:
        try:
            client = genai.Client(**get_gemini_client_kwargs(model=model_name))
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            if resp.text:
                return sanitize_script_punctuation(resp.text.strip(), outline_notes=notes)
        except Exception as exc:
            errors.append(f"{model_name}: {exc}")
            continue

    raise RuntimeError("AI 腳本生成失敗：\n" + "\n".join(errors))


def expand_story_script(
    current_script: str,
    topic: str = "",
    tone_id: str = "michelin_curious",
    target_word_count: int = 3500,
    model: str | None = None,
) -> str:
    """讀取現有腳本，針對情節簡略、對話欠缺或轉折過快的章節深入擴寫，大幅增加篇幅厚度。"""
    _load_dotenv()
    from google import genai
    from google.genai import types

    tone_sample = extract_tone_spoken_sample(load_tone_sample(tone_id))

    target_lines = max(20, round(target_word_count / 20))
    min_expand_words = int(target_word_count * 0.9)
    max_expand_words = int(target_word_count * 1.1)

    prompt = f"""你是一位頂級專題故事與紀錄片資深編劇。
下方是目前已經初步撰寫的一篇口白腳本。請你進行「深度情節擴寫與細節補強」，將其精準擴寫為目標約 {target_word_count} 字的深度故事：

【主題】
{topic if topic else "原腳本核心主題"}

【原始腳本口白】
{current_script.strip()}

【擴寫字數與篇幅嚴格限制（極重要）】
- 目標總字數：擴寫後全文必須嚴格控制在約 {target_word_count} 字左右（容許區間：{min_expand_words} ～ {max_expand_words} 字，嚴禁超出上限過度膨脹，亦不可擴寫不足）
- 擴寫後總行數：全文請維持在約 {target_lines} 行獨立口白左右（每行約 18~22 字）
- 擴寫重點：請精準針對情節薄弱或節奏跳躍處補充實質對峙、對白細節與關鍵歷史/技術數據，切忌漫無邊際冗長灌水，達到上述字數範圍即告完成！

【擴寫指令與原則】
1. 保留原本故事主線與精華亮點，在其基礎上進行「血肉充實」：
   - 在關鍵衝突處增加真實人物對峙、對白細節與心理交戰
   - 在技術或歷史轉折處補充關鍵歷史數據、對比與背後原理
   - 將原本幾句話草草帶過的情節展開為完整的對決與高潮
2. 標點符號與格式約束（極為嚴格）：
   - 全文標點符號只允許「，」、「？」、「！」（嚴禁句號「。」、頓號「、」、冒號「：」、引號、括號與破折號）。
   - 問號與感嘆號極度克制（每 10~15 句至多出現 1 次）。
   - 必須維持「一行一句獨立口白」（每行約 15~25 字，說完一句必須立即按下 Enter 換行，絕對嚴禁多句連成大長行）。
   - 【絕對嚴格禁止】輸出任何章節標題、幕次名稱或提示前綴（嚴禁出現「第一幕」、「第X幕」等結構標籤），每一行都必須是純口白！
   - 嚴禁把大綱場記唸出來：幕次標題、情緒標註（例如「強烈的荒謬感與好奇心」）、以及「讓觀眾思考／帶給觀眾／鋪陳出」等後設說明。
   - 【絕對嚴禁自稱「說書人」或「小編」】！全篇語氣人設嚴格遵照下方風格範本。
   - 外國人名、機構名一律中文通譯，避免英文。
   - 自然嵌入 OmniVoice 情緒標籤（如 [surprise-wa]、[sigh]、[question-ei] 等，每 4~6 句至多 1 個）。

【口吻風格參照（只模仿語氣與句式，禁止輸出結構標題或節奏公式名稱）】
{tone_sample if tone_sample else "請使用極具感染力、短句頓挫、反詰質疑後驚喜反轉的敘事風格。"}

請直接輸出擴寫後的完整逐行口白腳本，不要輸出任何前言或客套話，切勿自稱說書人："""

    config = types.GenerateContentConfig(
        temperature=0.75,
        tools=[{"google_search": {}}],
    )

    models_to_try = get_candidate_text_models(model)
    errors = []
    for model_name in models_to_try:
        try:
            client = genai.Client(**get_gemini_client_kwargs(model=model_name))
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

    raise RuntimeError("AI 腳本擴寫失敗：\n" + "\n".join(errors))


def extract_story_visual_anchors(
    topic: str,
    script_text: str,
    style_key: str = "",
    model: str | None = None,
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

        prompt = f"""You are a master concept artist and visual continuity director.
Analyze the story topic and script excerpt below.
Extract a CHARACTER & KEY ENTITY BIBLE and one ENVIRONMENT ANCHOR in high-detail ENGLISH.

{style_lock}

CRITICAL ENTITY CATEGORIZATION RULES:
1. DISTINGUISH PERSONS VS. INANIMATE OBJECTS/VEHICLES:
   - For HUMAN CHARACTERS (e.g., historical figures, CEOs, soldiers, civilians):
     Describe their realistic/chibi face, hairstyle, facial hair, body build, and era-appropriate clothing in the selected art style.
   - For INANIMATE OBJECTS, PROPS, PRODUCTS & VEHICLES (e.g., soda bottles/cans, warships, submarines, machinery, telescopes, aircraft, weapons):
     Describe their authentic mechanical structure, hull/chassis design, materials (metal, glass), brand logo, colors, and proportions.
2. STRICT NO-ANTHROPOMORPHISM RULE:
   - NEVER anthropomorphize inanimate objects or military vehicles!
   - DO NOT give warships, submarines, bottles, cans, or machines human eyes, faces, smiles, arms, hands, legs, or feet!
   - An object/vehicle must remain a physical, authentic non-living item/vehicle (even in stylized or chibi art styles, simplify the geometric shape and clean lines, but NEVER turn it into a walking creature with limbs).
3. Do not merge multiple entities into one entry. List up to 6 key recurring entities.
4. "environment_anchor" is the shared world, architecture, palette, and lighting — not an entity — and must match the locked art style (medium, line, color, lighting).

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
      "appearance": "English visual description. For humans: face, hair, clothing. For objects/vehicles: authentic physical model, materials, colors (NO face/limbs)."
    }}
  ],
  "environment_anchor": "English description of world, architecture, lighting..."
}}
"""
        for model_name in get_candidate_text_models(model):
            try:
                client = genai.Client(**get_gemini_client_kwargs(model=model_name))
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
    """呼叫 Gemini 依據專案全域視覺風格與視覺錨點，將中文旁白直接轉換為專業英文畫面出圖提示詞。"""
    if not narrations:
        return []

    from aivideo.visual_anchors import character_bible_for_prompts

    bible = character_bible_for_prompts(characters or [])

    try:
        from google import genai
        from google.genai import types

        tag_pattern = re.compile(r"\[[a-zA-Z0-9_\-]+\]")
        items_text = "\n".join([f"[{i+1}] {tag_pattern.sub('', n).strip()}" for i, n in enumerate(narrations)])
        
        clean_bible = bible.replace("educational storyboard", "2D animation").replace("educational panels", "clean 2D panels") if bible else ""
        clean_sub_anchor = subject_anchor.replace("educational storyboard", "2D animation").replace("educational panels", "clean 2D panels")
        clean_env_anchor = environment_anchor.replace("educational storyboard", "2D animation").replace("educational panels", "clean 2D panels")

        anchor_rules = ""
        if clean_bible or clean_sub_anchor or clean_env_anchor:
            if clean_bible:
                subject_rule = (
                    "CHARACTER & ENTITY BIBLE (include visual details ONLY when that entity actually appears in the scene; never force unused entities into the frame):\n"
                    f"{clean_bible}\n"
                    "- STRICT NO-ANTHROPOMORPHISM: Never give inanimate objects/ships/bottles human eyes, faces, arms, or legs."
                )
            else:
                subject_rule = f'- MAIN SUBJECT ANCHOR: Whenever the main protagonist/object appears, incorporate these specific physical details: "{clean_sub_anchor}"'
            env_rule = ""
            if clean_env_anchor:
                env_rule = f'\n- ENVIRONMENT & LIGHTING ANCHOR: Maintain this consistent background atmosphere and cinematic lighting palette: "{clean_env_anchor}"'
            anchor_rules = f"""
STRICT VISUAL CONTINUITY RULES (Apply to all scenes to maintain consistency):
{subject_rule}{env_rule}
"""

        style = resolve_style(style_key)
        style_lock = style_lock_instructions(style_key)
        prompt = f"""You are a master storyboard visual director and concept artist.
Analyze the following scene narrations from a video documentary.
Transform each scene narration into a compelling, evocative visual text-to-image prompt strictly in ENGLISH.

{style_lock}
{anchor_rules}

CRITICAL PROMPT CRAFTING REQUIREMENTS:
1. Every prompt MUST be written completely in ENGLISH.
2. Formulate the visual prompt strictly in the locked project art medium: {style["name"]}. Do NOT contradict it with unrelated art styles.
3. Translate abstract voiceover concepts into CONCRETE, VISUALLY STRIKING PHYSICAL SCENES: subjects, dynamic character action or expressive posture, tangible props, lighting, atmosphere, and camera framing (wide establishing shot, medium close-up, dramatic low angle) in 16:9 widescreen composition.
4. Keep inanimate objects strictly physical (never give objects cartoon human eyes, limbs, or faces).
5. NEVER include any dialogue, speech bubbles, quotes, text, subtitles, words, letters, logos, or watermarks.
6. Output EXACTLY a JSON array of strings containing exactly {len(narrations)} prompts in the same order as the input scenes:
[
  "wide establishing shot of [subject and action description], [lighting], [environment], 16:9 widescreen composition",
  "..."
]

Scenes:
{items_text}
"""
        for model_name in get_candidate_text_models():
            try:
                client = genai.Client(**get_gemini_client_kwargs(model=model_name))
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
                        result = []
                        for p in parsed:
                            p_text = str(p.get("image_prompt") if isinstance(p, dict) else p).strip()
                            p_text = re.sub(r"\b(?:educational storyboard|educational panels)\b", "2D cartoon illustration", p_text, flags=re.IGNORECASE)
                            result.append(p_text)
                        return result
            except Exception:
                continue
    except Exception:
        pass

    # 備援 (Fallback)
    fallbacks = []
    style = resolve_style(style_key)
    base_sub = subject_anchor if subject_anchor else "the central subject"
    base_env = environment_anchor if environment_anchor else f"{style['name']} environment"
    for _ in narrations:
        fallbacks.append(
            f"{style['name']} wide angle shot featuring {base_sub}, {base_env}, 16:9 widescreen composition"
        )
    return fallbacks


def translate_single_scene_prompt(
    narration: str,
    style_key: str = "",
    subject_anchor: str = "",
    environment_anchor: str = "",
    characters: list[dict[str, str]] | None = None,
) -> str:
    """為單一分鏡依據專案全域視覺風格與錨點，將中文旁白直接重新轉譯為高品質純英文出圖 Prompt。"""
    res = batch_generate_english_image_prompts(
        [narration],
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
        characters=characters,
        style_key=style_key,
    )
    return res[0] if res else ""


def batch_detect_pip_queries(
    narrations: list[str],
    topic: str = "",
    subject_anchor: str = "",
) -> list[str | None]:
    """呼叫 Gemini 批次分析各場景分鏡台詞，結合紀錄片主題與核心錨點，判定哪些場景適合搭配真實考據照片 (PiP)，輸出精準檢索詞或 None。"""
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

    context_lines = []
    if topic:
        context_lines.append(f"- Documentary Core Topic: {topic}")
    if subject_anchor:
        context_lines.append(f"- Core Subject Anchor & Era: {subject_anchor}")
    context_block = f"\nDOCUMENTARY CONTEXT:\n" + "\n".join(context_lines) + "\n" if context_lines else ""

    prompt = f"""You are a master archival visual researcher and senior documentary film archivist.
Analyze the following scene narrations for a documentary video.{context_block}
Your mission is to identify scenes that describe a SPECIFIC, CONCRETE, REAL-WORLD ENTITY where showing a REAL archival photograph, authentic blueprint, genuine historical document/contract, or news clipping (as a Picture-in-Picture card) will dramatically boost audience immersion and documentary credibility.

Scenes:
{json.dumps(scene_items, ensure_ascii=False, indent=2)}

CRITICAL QUERY GUIDELINES (STRICT SPECIFICITY, NO ABSTRACT TERMS):
1. ABSOLUTELY FORBIDDEN TERMS:
   - Do NOT output abstract concepts, emotions, or generic topics (e.g. "Cold War diplomacy", "naval power", "military tension", "secret trade", "space mystery", "ancient history"). Image archives and web engines return useless maps, random flags, or modern stock logos for these.
2. PRIORITY ENTITY TYPES (FOCUS ON AUTHENTIC ARCHIVAL EVIDENCE):
   - Priority 1: Genuine Historical Documents / Contracts / Blueprints / News Clippings (e.g., "Pepsi USSR barter trade agreement 1989", "Apollo 11 flight plan NASA", "Perkin-Elmer mirror polish blueprint").
   - Priority 2: Key Historical Figures / Decision Makers: Full official name with title or era (e.g., "Donald Kendall Pepsi CEO", "Mikhail Gorbachev portrait", "Burn-Jeng Lin TSMC", "Nancy Grace Roman astronomer").
   - Priority 3: Specific Vehicles / Ships / Spacecraft / Weapons: Exact official model, class, or NATO reporting name (e.g., "Project 613 Whiskey-class submarine", "KH-11 KENNEN reconnaissance satellite", "Soyuz TMA spacecraft", "Lockheed U-2 spy plane").
   - Priority 4: Specific Instruments / Technology / Facilities: Concrete device or facility (e.g., "ASML Twinscan immersion lithography", "Hubble primary mirror polishing Perkin-Elmer", "James Webb Space Telescope gold mirror").
   - Chinese-specific figures, organizations or locations: Provide English name or well-known Chinese keyword (e.g., "林本堅 浸潤式微影", "張忠謀 台積電", "ASML 光刻機").
3. WHEN TO RETURN NULL:
   - If the scene narration is generic commentary, transition, philosophical thought, or purely conceptual without a tangible real-world entity, return null.
4. SELECTIVITY:
   - Only 25%~45% of scenes deserve an authentic archival PiP card. Quality, credibility, and relevance over quantity.

OUTPUT FORMAT:
Return a JSON array of strings or nulls, with EXACTLY {len(narrations)} items corresponding to the scenes in order:
["Hubble primary mirror", null, "Donald Kendall Pepsi CEO", null]
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
    outline: str | None = None,
    metaphor_style: str = "fantasy",
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

    def _join_scene_sentences(lines: list[str]) -> str:
        processed = []
        for l in lines:
            t = l.strip()
            if not t:
                continue
            # 若句子末尾沒有任何標點符號，自動補上全形逗號
            if not t.endswith(("，", "、", "。", "！", "？", "!", "?", "；")):
                t += "，"
            processed.append(t)
        return "".join(processed)

    narrations = [_join_scene_sentences(c) for c in chunks]
    english_prompts = batch_generate_english_image_prompts(
        narrations,
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
        characters=characters,
        style_key=style_key,
    )
    pip_queries = batch_detect_pip_queries(
        narrations,
        topic=topic,
        subject_anchor=subject_anchor,
    )

    scenes: list[dict[str, object]] = []
    for idx, (chunk, narration) in enumerate(zip(chunks, narrations), start=1):
        img_prompt = (
            english_prompts[idx - 1]
            if idx - 1 < len(english_prompts)
            else "Cinematic wide angle shot, dramatic lighting, 16:9 widescreen composition"
        )
        q = pip_queries[idx - 1] if idx - 1 < len(pip_queries) else None

        scenes.append({
            "id": scene_folder_id(idx),
            "index": idx,
            "title": scene_title_from_narration(narration),
            "narration": narration,
            "sentences": list(chunk),
            "image_prompt": img_prompt,
            "pip_query": q,
        })

    from aivideo.acts import apply_acts_to_scenes, parse_outline_acts

    apply_acts_to_scenes(scenes, parse_outline_acts(outline or ""))
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
    voice_id: str = DEFAULT_VOICE_ID,
    subject_anchor: str = "",
    environment_anchor: str = "",
    characters: list[dict[str, str]] | None = None,
    image_model: str | None = None,
    custom_prompt: str | None = None,
    outline: str | None = None,
    tone_id: str | None = None,
    use_pip: bool = True,
    metaphor_style: str = "fantasy",
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

    from aivideo.fonts import subtitle_font_for_job
    from aivideo.job_files import save_job_config

    job_yaml = {
        "id": job_id,
        "title": title,
        "language": "zh-Hant",
        "voice_id": voice_id,
        "use_pip": bool(use_pip),
        "tone_id": tone_id or "",
        "metaphor_style": metaphor_style or "fantasy",
        "custom_prompt": custom_prompt or "",
        "outline": outline or "",
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
            "model": (image_model or os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image")).strip(),
            "model_final": (image_model or os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image")).strip(),
            "resolution": "1K",
            "aspect_ratio": "16:9",
            "style": style_key,
        },
        "style_prefix": style_cfg["prefix"],
        "style_negative": style_cfg["negative"],
        "subtitle": {
            "mode": "none",
            "font": subtitle_font_for_job(),
            "font_size": 48,
        },
        "kenburns": "slow_zoom_in",
    }
    save_job_config(job_dir, job_yaml)

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
            "act_index": s.get("act_index") or 0,
            "act_title": s.get("act_title") or "",
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
                "enabled": True,  # 預設啟用考據，出圖或一鍵全流程時自動下載生效
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
    """依據最新主體與環境錨點及專案全域風格，重新為現有 Job 的所有場景批次產生並更新英文提示詞 (Image Prompts)。"""
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

    style_key = ""
    try:
        from aivideo.job_files import load_job_config

        cfg = load_job_config(job_dir)
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
            scfg["image_prompt"] = str(new_prompts[idx])
            scfg.pop("visual_concept", None)
            with open(s_yaml_p, "w", encoding="utf-8") as f:
                yaml.safe_dump(scfg, f, allow_unicode=True, sort_keys=False)
            updated_count += 1

    return updated_count

