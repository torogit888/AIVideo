"""大綱幕次（Act）與鏡頭（Shot）兩層。"""

from __future__ import annotations

import re
from typing import Any

from aivideo.job_files import read_outline_text

_CN_NUM = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

ACT_HEAD_RE = re.compile(
    r"^#{1,3}\s*(?:第\s*)?([0-9一二三四五六七八九十]+)幕[：:\s\-—]*(.*)$",
    re.M,
)


def _parse_act_number(raw: str) -> int:
    raw = (raw or "").strip()
    if raw.isdigit():
        return int(raw)
    if raw in _CN_NUM:
        return _CN_NUM[raw]
    if raw.startswith("十") and len(raw) == 2:
        return 10 + _CN_NUM.get(raw[1], 0)
    return 0


def parse_outline_acts(text: str) -> list[dict[str, Any]]:
    """從 outline.md／大綱正文切出幕次標題與正文。"""
    if not text or not str(text).strip():
        return []
    matches = list(ACT_HEAD_RE.finditer(text))
    if not matches:
        return []
    acts: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        index = _parse_act_number(m.group(1)) or (i + 1)
        title = (m.group(2) or "").strip(" ：:-—") or f"第 {index} 幕"
        body = text[start:end].strip()
        acts.append({"index": index, "title": title, "body": body})
    return acts


def assign_acts(n_scenes: int, acts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """依幕次正文長度把 N 個鏡頭分到各幕；沒有大綱時全部算鏡頭。"""
    if n_scenes <= 0:
        return []
    if not acts:
        return [{"index": 0, "title": "鏡頭"} for _ in range(n_scenes)]

    weights = [max(1, len(str(a.get("body") or ""))) for a in acts]
    total_w = sum(weights) or len(acts)
    raw = [max(1, round(n_scenes * w / total_w)) for w in weights]
    while sum(raw) > n_scenes and max(raw) > 1:
        raw[raw.index(max(raw))] -= 1
    while sum(raw) < n_scenes:
        raw[raw.index(min(raw))] += 1

    out: list[dict[str, Any]] = []
    for act, count in zip(acts, raw):
        for _ in range(count):
            out.append({"index": int(act["index"]), "title": str(act["title"])})
    return out[:n_scenes]


def apply_acts_to_scenes(scenes: list[dict[str, Any]], acts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assigned = assign_acts(len(scenes), acts)
    for scene, act in zip(scenes, assigned):
        scene["act_index"] = act["index"]
        scene["act_title"] = act["title"]
    return scenes


def acts_from_job(job_dir) -> list[dict[str, Any]]:
    return parse_outline_acts(read_outline_text(job_dir))
