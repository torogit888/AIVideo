"""口白與字幕用字：yaml／SRT／編輯器存正確漢字；諧音與情緒標籤只在送 TTS 時處理。"""

from __future__ import annotations

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
