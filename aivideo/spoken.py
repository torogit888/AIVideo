"""口白與字幕用字：yaml／SRT／編輯器存正確漢字；諧音與情緒標籤只在送 TTS 時處理；口白標點清洗與人設去識別化集中於此。"""

from __future__ import annotations

from difflib import SequenceMatcher
import re

OMNIVOICE_TAG_RE = re.compile(r"\[[a-zA-Z0-9_\-]+\]")

PRONUNCIATION_WORD_MAPPINGS: dict[str, str] = {
    "企": "氣",
    "垃": "勒",
    "圾": "色",
    "角": "腳",
    "亞": "雅",
    "質": "直",
    "括": "瓜",
    "期": "棋",
    "微": "圍",
    "究": "舊",
    "擊": "集",
    "突": "圖",
    "暫": "戰",
    "艘": "騷",
    "蝸": "瓜",
    "綜": "縱",
}


def strip_omnivoice_tags(text: str) -> str:
    if not text:
        return ""
    return OMNIVOICE_TAG_RE.sub("", text).strip()


def apply_pronunciation_mapping(text: str) -> str:
    """將容易讀錯的繁體字換成諧音字，僅供 TTS 輸入。"""
    if not text:
        return ""
    for src, dst in PRONUNCIATION_WORD_MAPPINGS.items():
        text = text.replace(src, dst)
    return text


def prepare_tts_text(text: str) -> str:
    """送 OmniVoice：諧音 mapping，保留情緒標籤。"""
    return apply_pronunciation_mapping(text or "")


def prepare_subtitle_text(text: str) -> str:
    """字幕與畫面：正確漢字，剝離情緒標籤。"""
    return strip_omnivoice_tags(text or "")


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
    r"根據您的(核心)?指示|我將根據您的|以下為您(規劃|生成)|"
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
    text = OMNIVOICE_TAG_RE.sub("", line or "")
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
    """自動清理並嚴格規範口白標點符號與場記過濾。"""
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
        line = re.sub(r"[「」『』\"'“”‘’《》〈〉（）()]", "", line)
        line = re.sub(r"[、：:]", "，", line)
        line = re.sub(r"[—…]+", "，", line)
        line = re.sub(r"！+", "！", line)
        line = re.sub(r"？+", "？", line)
        line = re.sub(r"，+", "，", line)
        line = re.sub(r"^[，,]+", "", line).strip()
        if not line or is_non_spoken_script_line(line, outline_phrases):
            continue

        sub_lines = split_long_narration_line(line, max_chars=30)
        for sl in sub_lines:
            sl = re.sub(r"^[，,]+", "", sl).strip()
            if sl and not is_non_spoken_script_line(sl, outline_phrases):
                cleaned_lines.append(sl)

    return "\n".join(cleaned_lines)


def resolve_host_persona_name(user_prompt: str | None, default_name: str = "白兔") -> str:
    """從『故事要求 (user_prompt)』中解析頻道主自稱。"""
    if not user_prompt or not user_prompt.strip():
        return default_name
    text = user_prompt.strip()
    if re.search(r"(無自稱|不自稱|免自稱|直接破題)", text):
        return ""
    m = re.search(r"我是\s*([^\s，,。！!？?~～\n「」『』\"'（）()]{1,15})", text)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"(?:自稱|頻道(?:主|名|名稱)?)\s*[：:]\s*([^\s，,。！!？?~～\n]{1,15})", text)
    if m2:
        return m2.group(1).strip()
    return default_name


def deidentify_and_bind_tone(tone_text: str, host_name: str = "白兔") -> str:
    """將口吻範本中的特定 YouTuber 名字去識別化，並動態套入當前頻道主自稱。"""
    if not tone_text:
        return ""
    out = tone_text
    out = re.sub(r"(?m)^name:\s*.*$", "name: 專屬深度說書口吻", out)
    if host_name:
        out = re.sub(r"\{\s*(?:頻道主|說書人|主持人|YTR)\s*\}", host_name, out)
        out = re.sub(r"我是叉雞", f"我是{host_name}", out)
    else:
        out = re.sub(r"大家好[，,~\s]*我是\s*(?:\{\s*(?:頻道主|說書人|主持人|YTR)\s*\}|叉雞)[，,！!\s]*", "", out)
        out = re.sub(r"\{\s*(?:頻道主|說書人|主持人|YTR)\s*\}", "", out)
    return out


def _deidentify_extracted_narrator_name(text: str) -> str:
    """在萃取逐字稿口吻範本時，將開頭自稱自動正規化為『大家好，我是{頻道主}，』。"""
    if not text:
        return ""
    return re.sub(
        r"(大家好[，,~\s]*我是)\s*(?!\{\s*頻道主\s*\})([^\s，,。！!？?~～\n「」『』\"'（）()]{1,12})(?=[，,！!\s]|$)",
        r"\1{頻道主}",
        text,
    )

