from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any
from PIL import Image
import requests
import yaml

from aivideo.commands.check import _load_dotenv
from aivideo.gemini_image import get_gemini_client_kwargs
from aivideo.story_generator import TEXT_MODELS

REPO_ROOT = Path(__file__).resolve().parents[1]

VISION_REVIEW_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.7-flash",
)

WIKIMEDIA_HEADERS = {
    "User-Agent": "AIVideoDocBot/2.0 (https://github.com/aivideo/aivideo; documentary-research@aivideo-studio.org)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}


def search_nasa_video(query: str, limit: int = 3) -> list[dict[str, object]]:
    """呼叫 NASA 官方開放影音 API (images-api.nasa.gov) 檢索太空、航太、火箭發射與天文真實影片。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return []
    url = f"https://images-api.nasa.gov/search?q={urllib.parse.quote(clean_q)}&media_type=video"
    try:
        resp = requests.get(url, headers=WIKIMEDIA_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        items = resp.json().get("collection", {}).get("items", [])
        results: list[dict[str, object]] = []
        for it in items[: limit * 2]:
            data_list = it.get("data", [])
            href = it.get("href", "")
            links_list = it.get("links", [])
            if not data_list or not href:
                continue
            title = data_list[0].get("title", "")
            thumb_url = ""
            for lk in links_list:
                if lk.get("render") == "image" and lk.get("href"):
                    thumb_url = str(lk.get("href")).split("?")[0]
                    break
            try:
                c_resp = requests.get(href, headers=WIKIMEDIA_HEADERS, timeout=8)
                if c_resp.status_code != 200:
                    continue
                asset_urls = c_resp.json()
                if not isinstance(asset_urls, list):
                    continue
                mp4_urls = [str(u) for u in asset_urls if str(u).lower().endswith(".mp4") and "mobile" not in str(u).lower()]
                if not mp4_urls:
                    mp4_urls = [str(u) for u in asset_urls if str(u).lower().endswith((".mp4", ".webm", ".mov"))]
                if not mp4_urls:
                    continue
                # 優先挑選 medium / preview / 720p / orig
                chosen_url = mp4_urls[0]
                for u in mp4_urls:
                    ul = u.lower()
                    if any(tag in ul for tag in ("~medium.mp4", "~large.mp4", "~preview.mp4", "720", "1080")):
                        chosen_url = u
                        break
                results.append({
                    "title": title,
                    "url": chosen_url,
                    "thumbnail_url": thumb_url,
                    "source": "NASA 官方影片庫",
                    "width": 1920,
                    "height": 1080,
                    "mime": "video/mp4",
                    "media_type": "video",
                })
                if len(results) >= limit:
                    break
            except Exception:
                continue
        return results
    except Exception:
        return []


def search_wikimedia_video(query: str, limit: int = 3) -> list[dict[str, object]]:
    """呼叫 Wikimedia Commons API 檢索歷史新聞片、科學實驗、設備運作與公共領域真實影片。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return []

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{clean_q} filetype:video",
        "gsrnamespace": 6,
        "gsrlimit": 8,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|thumbMime",
        "iiurlwidth": 640,
        "format": "json",
    }
    url = f"https://commons.wikimedia.org/w/api.php?{urllib.parse.urlencode(params)}"
    try:
        resp = requests.get(url, headers=WIKIMEDIA_HEADERS, timeout=12)
        if resp.status_code != 200:
            return []
        pages = resp.json().get("query", {}).get("pages", {})
        if not pages:
            return []

        results: list[dict[str, object]] = []
        for _pid, pdata in pages.items():
            imginfo = pdata.get("imageinfo", [{}])[0]
            raw_url = str(imginfo.get("url", ""))
            mime = str(imginfo.get("mime", "")).lower()
            width = int(imginfo.get("width") or 0)
            height = int(imginfo.get("height") or 0)
            size_bytes = int(imginfo.get("size") or 0)
            thumb_url = str(imginfo.get("thumburl") or "")

            if not raw_url:
                continue
            if not any(v_m in mime for v_m in ("video/webm", "video/mp4", "application/ogg", "video/ogg")):
                continue
            # 排除過大 (> 120MB) 或過小解析度的影片，確保檢索與轉碼迅速
            if size_bytes > 120 * 1024 * 1024:
                continue
            if width >= 320 and height >= 200:
                results.append({
                    "title": pdata.get("title", clean_q),
                    "url": raw_url,
                    "thumbnail_url": thumb_url,
                    "width": width,
                    "height": height,
                    "mime": mime,
                    "source": "維基共享影片 (Wikimedia Video)",
                    "media_type": "video",
                })
                if len(results) >= limit:
                    break
        return results
    except Exception:
        return []


def search_internet_archive_video(query: str, limit: int = 3) -> list[dict[str, object]]:
    """呼叫 Internet Archive (archive.org) 檢索歷史新聞片、紀錄片與全網影片檔案。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return []
    q_str = f'({clean_q}) AND mediatype:(movies)'
    search_url = (
        f"https://archive.org/advancedsearch.php?q={urllib.parse.quote(q_str)}"
        f"&fl[]=identifier&fl[]=title&sort[]=downloads+desc&rows={limit * 2}&page=1&output=json"
    )
    try:
        resp = requests.get(search_url, headers=WIKIMEDIA_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        docs = resp.json().get("response", {}).get("docs", [])
        results: list[dict[str, object]] = []
        for doc in docs:
            ident = str(doc.get("identifier") or "").strip()
            title = str(doc.get("title") or clean_q).strip()
            if not ident:
                continue
            meta_url = f"https://archive.org/metadata/{urllib.parse.quote(ident)}"
            try:
                m_resp = requests.get(meta_url, headers=WIKIMEDIA_HEADERS, timeout=8)
                if m_resp.status_code != 200:
                    continue
                files = m_resp.json().get("files", [])
                chosen_file = None
                for f in files:
                    fname = str(f.get("name") or "")
                    fmt = str(f.get("format") or "").lower()
                    size_b = int(f.get("size") or 0) if str(f.get("size") or "").isdigit() else 0
                    if fname.lower().endswith(".mp4") and (0 < size_b <= 150 * 1024 * 1024):
                        chosen_file = fname
                        if "512kb" in fmt or "h.264" in fmt or "mpeg4" in fmt:
                            break
                if chosen_file:
                    dl_url = f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(chosen_file)}"
                    thumb_url = f"https://archive.org/services/img/{urllib.parse.quote(ident)}"
                    results.append({
                        "title": title,
                        "url": dl_url,
                        "thumbnail_url": thumb_url,
                        "source": "Internet Archive 歷史影片庫",
                        "width": 1280,
                        "height": 720,
                        "mime": "video/mp4",
                        "media_type": "video",
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                continue
        return results
    except Exception:
        return []


def search_youtube_video(query: str, limit: int = 4) -> list[dict[str, object]]:
    """透過 yt-dlp 內建之 YouTube 搜尋器 (ytsearch) 檢索歷史新聞片、紀錄片與真實動態影片。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', "", query or "").strip()
    if not clean_q or not shutil.which("yt-dlp"):
        return []
    try:
        fetch_n = max(4, limit * 2)
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--flat-playlist",
            "--no-warnings",
            f"ytsearch{fetch_n}:{clean_q}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=18)
        if proc.returncode != 0 or not proc.stdout:
            return []
        candidates: list[dict[str, object]] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            vid = str(data.get("id") or "").strip()
            raw_u = str(data.get("url") or "").strip()
            if not vid and not raw_u:
                continue
            video_url = raw_u if raw_u.startswith("http") else f"https://www.youtube.com/watch?v={vid}"
            dur = float(data.get("duration") or 0)
            # 過濾過短 (< 4秒) 或超過 20 分鐘的長直播/整部電影，確保擷取迅速且聚焦
            if dur > 0 and (dur < 4 or dur > 1200):
                continue
            thumbs = data.get("thumbnails") if isinstance(data.get("thumbnails"), list) else []
            thumb_u = ""
            if thumbs and isinstance(thumbs[-1], dict):
                thumb_u = str(thumbs[-1].get("url") or "").strip()
            if not thumb_u and vid:
                thumb_u = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            candidates.append(
                {
                    "title": str(data.get("title") or clean_q),
                    "url": video_url,
                    "thumbnail_url": thumb_u,
                    "source": "YouTube 影音庫",
                    "width": 1920,
                    "height": 1080,
                    "mime": "video/mp4",
                    "media_type": "video",
                }
            )
            if len(candidates) >= limit:
                break
        return candidates
    except Exception:
        return []


def search_duckduckgo_video(query: str, limit: int = 4) -> list[dict[str, object]]:
    """透過全網影片檢索（優先使用 YouTube 影音搜尋，再輔以 DuckDuckGo Videos）搜尋相關影片候選。"""
    yt_res = search_youtube_video(query, limit=limit)
    if len(yt_res) >= limit:
        return yt_res[:limit]

    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return yt_res
    try:
        url = f"https://duckduckgo.com/?q={urllib.parse.quote(clean_q)}&iax=videos&ia=videos"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        res = requests.get(url, headers=headers, timeout=6)
        m = re.search(r'vqd=([\"\']?)([\d-]+)\1', res.text)
        if not m:
            return []
        vqd = m.group(2)
        api_url = f"https://duckduckgo.com/v.js?l=wt-wt&o=json&q={urllib.parse.quote(clean_q)}&vqd={vqd}&f=,,,&p=1"
        resp = requests.get(api_url, headers=headers, timeout=6)
        if resp.status_code != 200:
            return []
        items = resp.json().get("results", [])
        candidates: list[dict[str, object]] = []
        has_ytdlp = shutil.which("yt-dlp") is not None
        for it in items:
            content_url = str(it.get("content") or "").strip()
            if not content_url:
                continue
            # 若為直鏈 mp4/webm，或系統有安裝 yt-dlp 可解析全網影片網址，皆納入候選
            is_direct = any(content_url.lower().split("?")[0].endswith(ext) for ext in (".mp4", ".webm", ".mov", ".ogv"))
            if not is_direct and not has_ytdlp:
                continue
            images_dict = it.get("images") if isinstance(it.get("images"), dict) else {}
            thumb = str(images_dict.get("large") or images_dict.get("medium") or images_dict.get("small") or "")
            candidates.append({
                "title": str(it.get("title") or clean_q),
                "url": content_url,
                "thumbnail_url": thumb,
                "source": f"全網影片 ({it.get('provider') or 'Web Video'})",
                "width": 1280,
                "height": 720,
                "mime": "video/mp4",
                "media_type": "video",
            })
            if len(candidates) >= limit:
                break
        return candidates
    except Exception:
        return []


def search_nasa_image(query: str, limit: int = 4) -> list[dict[str, object]]:
    """呼叫 NASA 官方開放影像 API (images-api.nasa.gov) 檢索高畫質太空、航太與天文真實照片。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return []
    url = f"https://images-api.nasa.gov/search?q={urllib.parse.quote(clean_q)}&media_type=image"
    try:
        resp = requests.get(url, headers=WIKIMEDIA_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        items = resp.json().get("collection", {}).get("items", [])
        results = []
        for it in items[:limit]:
            data_list = it.get("data", [])
            links_list = it.get("links", [])
            if not data_list or not links_list:
                continue
            title = data_list[0].get("title", "")
            img_url = str(links_list[0].get("href", "")).split("?")[0]
            if img_url:
                results.append({
                    "title": title,
                    "url": img_url,
                    "source": "NASA 官方影像庫",
                    "width": 1920,
                    "height": 1080,
                    "mime": "image/jpeg",
                })
        return results
    except Exception:
        return []


def is_wikipedia_title_relevant(query: str, title: str) -> bool:
    """
    核驗維基百科搜尋回傳的條目標題是否與使用者檢索詞具有實質語意相關性。
    嚴格防範「莫斯科街頭」因模糊檢索被硬配成「莫斯科戰役」，或人物查詢命中「List of people with...」等列表頁的問題。
    """
    q = query.strip().lower()
    t = title.strip().lower()
    if not q or not t:
        return False

    # 0. 嚴格排除維基百科匯總列表頁（例如 "List of people with bipolar disorder"），避免抓出列表內無關人物的照片
    list_prefixes = ("list of ", "lists of ", "index of ", "outline of ", "glossary of ", "timeline of ", "category:")
    if not any(q.startswith(p) for p in list_prefixes):
        if any(t.startswith(p) for p in list_prefixes) or "列表" in t:
            return False

    # 1. 衝突語意過濾：若搜尋詞不含軍事衝突/影視詞，但標題卻包含，直接判定為主題偏移
    conflict_categories = [
        (["battle", "war", "戰役", "战役", "戰爭", "战争", "作戰", "作战", "戰鬥", "战斗", "海戰", "空戰"], ["戰", "战", "war", "battle"]),
        (["movie", "film", "電影", "电影", "電視劇", "电视剧"], ["影", "劇", "剧", "film", "movie"]),
    ]
    for trigger_terms, search_check in conflict_categories:
        if not any(sc in q for sc in search_check):
            if any(tt in t for tt in trigger_terms):
                return False

    # 2. 完全匹配
    if q == t:
        return True

    # 3. 標題完全包含使用者查詢詞（例如 查詢「街頭藝術」，標題為「莫斯科街頭藝術」）
    if q in t:
        return True

    # 4. 標題是查詢詞的子字串（例如 查詢 "Bernard Loiseau French chef portrait"，標題是 "Bernard Loiseau"）
    if t in q:
        # 英文條目若至少含一個完整專有單詞且長於 4 字元，或中文條目與查詢詞長度相近，視為命中核心實體
        t_en_words = re.findall(r"[a-z0-9]{3,}", t)
        if t_en_words and len(t) >= 5:
            return True
        if len(q) - len(t) <= 1:
            return True
        return False

    # 5. 分別針對中文字符與英文「完整單詞」計算覆蓋率（絕不可將英文拆成單一字母 a~z 比對）
    q_zh = set(re.findall(r"[\u4e00-\u9fa5]", q))
    t_zh = set(re.findall(r"[\u4e00-\u9fa5]", t))
    if q_zh:
        return (len(q_zh & t_zh) / len(q_zh)) >= 0.80

    stop_en = {
        "the", "and", "for", "with", "from", "in", "of", "on", "at", "to", "by", "during", "after",
        "post", "pre", "early", "late", "old", "new", "vintage", "classic", "authentic", "famous",
        "portrait", "photo", "photograph", "image", "picture", "history", "historical", "historic",
        "queue", "line", "scene", "view", "building", "exterior", "interior", "archive", "archival",
    }
    raw_q_words = [
        w for w in re.findall(r"[a-z0-9]{2,}", q)
        if w not in stop_en and not re.fullmatch(r"\d{4}s?", w)
    ]
    raw_t_words = [
        w for w in re.findall(r"[a-z0-9]{2,}", t)
        if w not in stop_en and not re.fullmatch(r"\d{4}s?", w)
    ]
    if not raw_q_words or not raw_t_words:
        return False

    # 同義詞正規化（例如 British / Britain / UK <-> United Kingdom）
    synonym_map = {
        "british": {"british", "britain", "uk", "united", "kingdom"},
        "britain": {"british", "britain", "uk", "united", "kingdom"},
        "uk": {"british", "britain", "uk", "united", "kingdom"},
        "soviet": {"soviet", "ussr", "union"},
        "ussr": {"soviet", "ussr", "union"},
        "american": {"american", "usa", "united", "states"},
        "usa": {"american", "usa", "united", "states"},
    }
    expanded_q: set[str] = set(raw_q_words)
    for w in list(raw_q_words):
        if w in synonym_map:
            expanded_q |= synonym_map[w]

    t_set = set(raw_t_words)
    overlap_q = sum(1 for w in raw_q_words if w in t_set or bool(synonym_map.get(w, set()) & t_set)) / len(raw_q_words)
    overlap_t = sum(1 for w in t_set if w in expanded_q) / len(t_set)
    return overlap_q >= 0.50 or overlap_t >= 0.65 or (len(t_set & expanded_q) >= 2)


def build_progressive_search_queries(query: str) -> list[str]:
    """
    將過長的考據檢索詞（如 'Post-war British food rationing queue 1951'）
    拆解為由精確到核心的多層次檢索詞，避免圖庫因嚴格 AND 交集而回傳 0 筆。
    """
    clean = re.sub(r'["\'\(\)\[\]]', " ", query or "").strip()
    clean = re.sub(r"\s+", " ", clean)
    if not clean:
        return []

    variants: list[str] = [clean]

    # 第 2 層：移除年份 (1951, 1950s)、時代前綴 (Post-war, Pre-war) 與圖片通用修飾詞
    stripped = re.sub(
        r"\b(?:post-war|pre-war|wartime|postwar|prewar|18\d\d|19\d\d|20\d\d|\d{4}s|"
        r"vintage|historical|historic|authentic|archival|archive|photograph|photo|"
        r"picture|portrait|image|scene|view|footage|early|late|old|classic|famous)\b",
        " ",
        clean,
        flags=re.IGNORECASE,
    )
    stripped = re.sub(r"[-–—]+", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if stripped and stripped.lower() not in {v.lower() for v in variants}:
        variants.append(stripped)

    # 第 3 層：若移除修飾詞後仍有 4 個字以上，再移除場景尾綴詞（如 queue, building, street, interior 等）或取前 3 個核心詞
    words = (stripped or clean).split()
    tail_scene_words = {"queue", "line", "building", "exterior", "interior", "room", "office", "crowd", "people"}
    core_words = [w for w in words if w.lower() not in tail_scene_words]
    if core_words and len(core_words) < len(words):
        core_q = " ".join(core_words).strip()
        if core_q and core_q.lower() not in {v.lower() for v in variants}:
            variants.append(core_q)

    if len(core_words) > 3:
        short_q = " ".join(core_words[:3]).strip()
        if short_q and short_q.lower() not in {v.lower() for v in variants}:
            variants.append(short_q)

    if len(core_words) > 2:
        two_q = " ".join(core_words[:2]).strip()
        if two_q and two_q.lower() not in {v.lower() for v in variants}:
            variants.append(two_q)

    return variants


def translate_entity_query_to_en(query: str) -> str | None:
    """若檢索詞為中文，轉譯出最適歷史考據英文名（供維基共享資源/NASA/LOC英文庫檢索真實照片）。"""
    clean_q = query.strip()
    if not clean_q:
        return None

    # 如果本身主要由英文構成，直接使用
    if not any('\u4e00' <= char <= '\u9fa5' for char in clean_q):
        return clean_q

    # 1. 常見歷史紀錄片實體快速對照表
    common_terms = {
        "莫斯科街頭": "Moscow street",
        "莫斯科街道": "Moscow street",
        "莫斯科街景": "Moscow street view",
        "紅場": "Red Square Moscow",
        "克里姆林宮": "Moscow Kremlin",
        "冷戰": "Cold War",
        "蘇聯潛艇": "Soviet submarine",
        "蘇聯海軍": "Soviet Navy",
        "蘇聯解體": "Dissolution of Soviet Union",
        "百事可樂": "Pepsi",
        "白宮": "White House",
        "五角大廈": "Pentagon",
        "阿波羅11號": "Apollo 11",
        "哈伯望遠鏡": "Hubble Space Telescope",
    }
    if clean_q in common_terms:
        return common_terms[clean_q]

    # 2. 嘗試呼叫 Gemini 進行精準名詞翻譯
    try:
        from google import genai
        from google.genai import types

        for model_name in ("gemini-3.8-flash", "gemini-3.7-flash"):
            try:
                client = genai.Client(**get_gemini_client_kwargs(model=model_name))
                resp = client.models.generate_content(
                    model=model_name,
                    contents=f"Translate this documentary historical scene/entity into 1 precise English photo search query (nouns only, max 4 words, e.g. '莫斯科街頭' -> 'Moscow street'):\n{clean_q}",
                    config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=25),
                )
                if resp.text:
                    en = re.sub(r'["\'\.\n]', '', resp.text).strip()
                    if en and not any('\u4e00' <= c <= '\u9fa5' for c in en):
                        return en
            except Exception:
                continue
    except Exception:
        pass
    return None


def search_wikipedia_summary_image(query: str, lang: str = "en") -> dict[str, object] | None:
    """呼叫維基百科 API 取得條目代表圖。先透過 search 模糊匹配最適條目名，再驗證相關度後取原圖。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return None

    target_title = None
    search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(clean_q)}&format=json&srlimit=5"
    try:
        s_resp = requests.get(search_url, headers=WIKIMEDIA_HEADERS, timeout=6)
        if s_resp.status_code == 200:
            s_data = s_resp.json().get("query", {}).get("search", [])
            for it in s_data:
                cand_title = it.get("title", "")
                if is_wikipedia_title_relevant(clean_q, cand_title):
                    target_title = cand_title
                    break
    except Exception:
        pass

    # 若維基百科候選條目皆不相關（如「莫斯科街頭」回傳「莫斯科戰役」），果斷放棄避免歪樓
    if not target_title:
        return None

    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(target_title)}"
    try:
        resp = requests.get(url, headers=WIKIMEDIA_HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            orig = data.get("originalimage", {})
            img_url = str(orig.get("source", "")).split("?")[0]
            # 排除 .svg 向量商標或旗幟（例如 Guinness_logo_dark_text.svg.png）
            if img_url and ".svg" not in img_url.lower():
                return {
                    "title": data.get("title", target_title),
                    "url": img_url,
                    "source": f"維基百科條目 ({lang.upper()})",
                    "width": orig.get("width", 1024),
                    "height": orig.get("height", 768),
                    "mime": "image/jpeg",
                }
    except Exception:
        pass
    return None


def search_wikipedia_article_images(query: str, lang: str = "en", limit: int = 4) -> list[dict[str, object]]:
    """
    檢索與關鍵字相關的維基百科條目中「內嵌的所有真實歷史照片」（突破 summary API 只抓右上角單張 Logo 的限制）。
    """
    clean_q = re.sub(r'["\'\(\)\[\]]', "", query or "").strip()
    if not clean_q:
        return []

    search_url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote(clean_q)}&format=json&srlimit=3"
    )
    target_titles: list[str] = []
    try:
        s_resp = requests.get(search_url, headers=WIKIMEDIA_HEADERS, timeout=6)
        if s_resp.status_code == 200:
            for it in s_resp.json().get("query", {}).get("search", []):
                cand_t = str(it.get("title") or "").strip()
                if cand_t and is_wikipedia_title_relevant(clean_q, cand_t):
                    target_titles.append(cand_t)
                    if len(target_titles) >= 2:
                        break
    except Exception:
        pass

    if not target_titles:
        return []

    results: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    skip_words = ("logo", "icon", "flag", "coat_of_arms", "symbol", "map", "commons-logo", "wikimedia", "ambox", "question_book")

    for t_title in target_titles:
        params = {
            "action": "query",
            "titles": t_title,
            "generator": "images",
            "gimlimit": 12,
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "format": "json",
        }
        api_u = f"https://{lang}.wikipedia.org/w/api.php?{urllib.parse.urlencode(params)}"
        try:
            r = requests.get(api_u, headers=WIKIMEDIA_HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            pages = r.json().get("query", {}).get("pages", {})
            for _pid, pdata in pages.items():
                f_title = str(pdata.get("title") or "")
                imginfo = (pdata.get("imageinfo") or [{}])[0]
                raw_url = str(imginfo.get("url") or "").split("?")[0]
                mime = str(imginfo.get("mime") or "").lower()
                w = int(imginfo.get("width") or 0)
                h = int(imginfo.get("height") or 0)
                if not raw_url or raw_url in seen_urls:
                    continue
                if ".svg" in raw_url.lower() or "svg" in mime:
                    continue
                if any(sw in f_title.lower() or sw in raw_url.lower() for sw in skip_words):
                    continue
                if ("image/jpeg" in mime or "image/png" in mime or "image/webp" in mime) and w >= 320 and h >= 220:
                    seen_urls.add(raw_url)
                    results.append(
                        {
                            "title": f"{t_title} - {f_title.replace('File:', '')}",
                            "url": raw_url,
                            "source": f"維基百科內文圖庫 ({lang.upper()})",
                            "width": w,
                            "height": h,
                            "mime": mime,
                        }
                    )
                    if len(results) >= limit:
                        return results
        except Exception:
            continue
    return results


def _unescape_google_url(raw: str) -> str:
    text = raw or ""
    text = (
        text.replace("\\u003d", "=")
        .replace("\\u0026", "&")
        .replace("\\u002f", "/")
        .replace("\\u003a", ":")
        .replace("\\u003f", "?")
        .replace("\\/", "/")
    )
    try:
        import html
        text = html.unescape(text)
    except Exception:
        pass
    return text.strip()


def search_google_image(query: str, limit: int = 5) -> list[dict[str, object]]:
    """直接透過 Google 圖片搜尋 (Google Images) 檢索全網歷史、新聞、人物與事件照片。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', "", query or "").strip()
    if not clean_q:
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
    }
    url = f"https://www.google.com/search?q={urllib.parse.quote(clean_q)}&tbm=isch&hl=en&gl=us"
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200 or not resp.text:
            return []
        html_text = resp.text
        candidates: list[dict[str, object]] = []
        seen: set[str] = set()

        # 解析 Google Images 內嵌的 (縮圖, 原圖, 高, 寬) 結構
        pair_pattern = re.compile(
            r'\["(https://encrypted-tbn0\.gstatic\.com/images\?[^"]+)",\d+,\d+\],\s*\["(https?://[^"]+)",(\d+),(\d+)\]'
        )
        for m in pair_pattern.finditer(html_text):
            thumb_u = _unescape_google_url(m.group(1))
            orig_u = _unescape_google_url(m.group(2))
            h = int(m.group(3) or 0)
            w = int(m.group(4) or 0)
            if not orig_u or orig_u in seen:
                continue
            if any(skip in orig_u.lower() for skip in ("gstatic.com", "google.com", "googleapis.com", ".svg")):
                continue
            if w < 300 or h < 200:
                continue
            # 嘗試從後方文字片段提取圖片標題
            tail_slice = html_text[m.end() : m.end() + 700]
            title_m = re.search(r'"2003":\[null,"[^"]*","[^"]*","([^"]+)"', tail_slice)
            if not title_m:
                title_m = re.search(r'\["([^"\[\]]{6,120})",\s*"https?://', tail_slice)
            title = _unescape_google_url(title_m.group(1)) if title_m else clean_q
            seen.add(orig_u)
            candidates.append(
                {
                    "title": title,
                    "url": orig_u,
                    "thumbnail_url": thumb_u,
                    "source": "Google 圖片 (Google Images)",
                    "width": w,
                    "height": h,
                    "mime": "image/jpeg",
                }
            )
            if len(candidates) >= limit:
                return candidates

        # 備援正則：若頁面採用新版 udm=2 結構，直接擷取高解析度圖檔元組
        fallback_pattern = re.compile(
            r'\["(https?://[^"\s\\]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\s\\]*)?)",(\d+),(\d+)\]',
            flags=re.IGNORECASE,
        )
        for m in fallback_pattern.finditer(html_text):
            orig_u = _unescape_google_url(m.group(1))
            h = int(m.group(2) or 0)
            w = int(m.group(3) or 0)
            if not orig_u or orig_u in seen:
                continue
            if any(skip in orig_u.lower() for skip in ("gstatic.com", "google.com", "googleapis.com", "favicon", "logo")):
                continue
            if w >= 320 and h >= 220:
                seen.add(orig_u)
                candidates.append(
                    {
                        "title": clean_q,
                        "url": orig_u,
                        "thumbnail_url": orig_u,
                        "source": "Google 圖片 (Google Images)",
                        "width": w,
                        "height": h,
                        "mime": "image/jpeg",
                    }
                )
                if len(candidates) >= limit:
                    break
        return candidates
    except Exception:
        return []


def search_duckduckgo_image(query: str, limit: int = 3) -> list[dict[str, object]]:
    """透過全網即時圖片檢索真實歷史、科技、新聞與事件照片。"""
    return search_google_image(query, limit=limit)


def search_loc_image(query: str) -> dict[str, object] | None:
    """呼叫美國國會圖書館 (Library of Congress) 開放 API 檢索公有領域高畫質歷史原版照片。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return None
    url = f"https://www.loc.gov/photos/?q={urllib.parse.quote(clean_q)}&fo=json"
    try:
        resp = requests.get(url, headers=WIKIMEDIA_HEADERS, timeout=8)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            for it in results[:4]:
                imgs = it.get("image_url", [])
                if imgs and isinstance(imgs, list):
                    img_url = imgs[-1]
                    if img_url:
                        return {
                            "title": it.get("title", clean_q),
                            "url": img_url,
                            "source": "美國國會圖書館 (Library of Congress)",
                            "width": 1280,
                            "height": 720,
                            "mime": "image/jpeg",
                        }
    except Exception:
        pass
    return None


def search_wikimedia_images(query: str, limit: int = 4) -> list[dict[str, object]]:
    """呼叫 Wikimedia Commons API 檢索公有領域高解析度真實攝影或檔案照片（回傳多筆候選）。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return []

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": clean_q,
        "gsrnamespace": 6,  # 檔案命名空間
        "gsrlimit": max(8, limit * 2),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "format": "json",
    }
    url = f"https://commons.wikimedia.org/w/api.php?{urllib.parse.urlencode(params)}"
    try:
        resp = requests.get(url, headers=WIKIMEDIA_HEADERS, timeout=12)
        if resp.status_code != 200:
            return []
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return []

        # 優先挑選解析度合適且為常見圖檔格式的圖片
        candidates: list[dict[str, object]] = []
        for _pid, pdata in pages.items():
            imginfo = pdata.get("imageinfo", [{}])[0]
            raw_url = str(imginfo.get("url", ""))
            img_url = raw_url.split("?")[0] if raw_url else ""
            mime = imginfo.get("mime", "").lower()
            width = imginfo.get("width", 0)
            height = imginfo.get("height", 0)

            # 排除向量圖、音訊、pdf 等
            if img_url and ("image/jpeg" in mime or "image/png" in mime or "image/webp" in mime):
                # 排除太小的圖示 (小於 300px)
                if width >= 300 and height >= 200:
                    candidates.append({
                        "title": pdata.get("title", ""),
                        "url": img_url,
                        "width": width,
                        "height": height,
                        "mime": mime,
                        "source": "維基共享資源 (Wikimedia)",
                    })
                    if len(candidates) >= limit:
                        break

        return candidates
    except Exception:
        return []


def search_wikimedia_image(query: str) -> dict[str, object] | None:
    """向下相容單筆回傳輔助函式。"""
    cands = search_wikimedia_images(query, limit=1)
    return cands[0] if cands else None


def score_candidate_image(cand: dict[str, object], query: str, en_query: str | None = None) -> float:
    """評估候選圖片與使用者檢索詞的精準契合度評分，確保挑選最貼切真實歷史照片。"""
    title = str(cand.get("title") or "").lower()
    source = str(cand.get("source") or "")
    q = query.lower()
    en_q = (en_query or "").lower()

    score = 50.0

    # 1. 場景/街頭特徵詞比對
    street_keywords = ("街頭", "街景", "街道", "street", "streets")
    if any(k in q for k in street_keywords) or any(k in en_q for k in street_keywords):
        if any(w in title for w in ("street", "streets", "avenue", "boulevard", "square", "road", "view", "city", "building", "街", "路", "廣場", "广场")):
            score += 35.0
        if any(w in title for w in ("dog", "dogs", "cat", "stray", "animal", "pet", "hound", "犬", "狗")):
            score -= 60.0

    # 2. 衝突詞扣分（僅針對完整單詞 battle/war，且排除 post-war / wartime / rationing 等歷史時期詞）
    if not any(w in q for w in ("戰", "战", "war", "battle", "rationing", "soviet", "cold")):
        if re.search(r"\b(battle|warfare|combat)\b", title) or any(w in title for w in ("戰役", "战役", "海戰", "作戰")):
            score -= 80.0

    # 2b. 標題命中檢索核心單詞加分（確保命中 rationing / queue 的檔案排在最前面）
    q_tokens = [w for w in re.findall(r"[a-z0-9]{3,}", f"{q} {en_q}") if w not in {"post", "war", "the", "and", "for", "with", "1950s"}]
    if q_tokens:
        matched = sum(1 for w in set(q_tokens) if w in title)
        score += matched * 18.0

    # 3. 來源加權：優先採用 Google 圖片與全網真實照片，Wikimedia / NASA / LOC 次之，純維基百科條目代表圖排最後
    if "Google 圖片" in source or "全網圖片" in source:
        score += 32.0
    elif "Wikimedia" in source or "維基共享" in source:
        score += 20.0
    elif "NASA" in source or "國會圖書館" in source:
        score += 20.0
    elif "維基百科條目" in source:
        score -= 20.0

    # 4. 解析度與尺寸加分
    width = int(cand.get("width") or 0)
    height = int(cand.get("height") or 0)
    if width >= 1200 and height >= 700:
        score += 10.0

    return score


def search_all_source_candidates(query: str, limit: int = 6) -> list[dict[str, object]]:
    """跨多個高可信來源（NASA 官方影像庫、全網新聞與歷史照片、中英文維基百科、美國國會圖書館、維基共享資源）聚合檢索真實照片。"""
    candidates: list[dict[str, object]] = []
    seen_urls: set[str] = set()

    clean_q = query.strip()
    if not clean_q:
        return []

    # 取得英文考據詞（若輸入為中文），並展開為漸進式搜尋詞（由精確長詞 -> 核心短詞）
    en_q = translate_entity_query_to_en(clean_q)
    base_en = en_q if (en_q and en_q != clean_q) else clean_q
    progressive_terms = build_progressive_search_queries(base_en)
    if clean_q not in progressive_terms:
        progressive_terms.append(clean_q)

    # 1. 第一優先：Google 圖片搜尋 (若環境可直連) 與 Wikimedia Commons 原版歷史攝影檔案（依漸進式關鍵字檢索）
    for term in progressive_terms[:2]:
        for g_item in search_google_image(term, limit=3):
            if g_item["url"] not in seen_urls:
                seen_urls.add(g_item["url"])
                candidates.append(g_item)

    # 2. 太空、天文、科技詞彙優先呼叫 NASA 官方圖庫
    space_keywords = {"space", "telescope", "nasa", "galaxy", "satellite", "star", "hubble", "roman", "webb", "planet", "orbit", "astronaut", "mars", "moon"}
    q_lower = clean_q.lower()
    if any(k in q_lower for k in space_keywords) or (en_q and any(k in en_q.lower() for k in space_keywords)):
        for term in progressive_terms[:2]:
            for it in search_nasa_image(term, limit=3):
                if it["url"] not in seen_urls:
                    seen_urls.add(it["url"])
                    candidates.append(it)

    # 3. 檢索 Wikimedia Commons 歷史照片與檔案庫（由完整詞漸進退回核心名詞，一旦找到足夠候選即停止退化，避免退回過廣的 2 字詞）
    for term in progressive_terms:
        for w_item in search_wikimedia_images(term, limit=4):
            if w_item["url"] not in seen_urls:
                seen_urls.add(w_item["url"])
                candidates.append(w_item)
        if len(candidates) >= 3:
            break

    # 4. 檢索英文與中文維基百科條目內嵌的所有真實歷史照片（排除 .svg 商標與圖示）
    if len(candidates) < limit:
        for term in progressive_terms[:3]:
            for art_img in search_wikipedia_article_images(term, lang="en", limit=3):
                if art_img["url"] not in seen_urls:
                    seen_urls.add(art_img["url"])
                    candidates.append(art_img)
            if len(candidates) >= limit:
                break

    # 5. 檢索美國國會圖書館歷史檔案 (Library of Congress)
    if len(candidates) < limit:
        for term in progressive_terms[:2]:
            loc_img = search_loc_image(term)
            if loc_img and loc_img["url"] not in seen_urls:
                seen_urls.add(loc_img["url"])
                candidates.append(loc_img)
                break

    # 6. 最後備援：維基百科條目首圖（已排除 .svg 商標）
    if len(candidates) < limit:
        for term in progressive_terms[:2]:
            en_img = search_wikipedia_summary_image(term, lang="en")
            if en_img and en_img["url"] not in seen_urls:
                seen_urls.add(en_img["url"])
                candidates.append(en_img)
                break
        zh_img = search_wikipedia_summary_image(clean_q, lang="zh")
        if zh_img and zh_img["url"] not in seen_urls:
            seen_urls.add(zh_img["url"])
            candidates.append(zh_img)

    # 依契合度打分智能排序，挑選最貼近真實場景與實體的原版照片
    candidates.sort(key=lambda c: score_candidate_image(c, clean_q, en_q), reverse=True)
    return candidates[:limit]


def search_all_source_video_candidates(query: str, limit: int = 6) -> list[dict[str, object]]:
    """跨全網來源（NASA 影音庫、Wikimedia Commons 影片、Internet Archive 歷史影片、全網影片搜尋）聚合檢索真實考據影片。"""
    candidates: list[dict[str, object]] = []
    seen_urls: set[str] = set()

    clean_q = query.strip()
    if not clean_q:
        return []

    en_q = translate_entity_query_to_en(clean_q)
    base_en = en_q if (en_q and en_q != clean_q) else clean_q
    search_terms = build_progressive_search_queries(base_en)
    if clean_q not in search_terms:
        search_terms.append(clean_q)

    # 1. 太空、航太、天文詞彙優先呼叫 NASA 官方影片庫
    space_keywords = {"space", "telescope", "nasa", "galaxy", "satellite", "star", "hubble", "roman", "webb", "planet", "orbit", "astronaut", "mars", "moon", "apollo", "rocket", "launch"}
    q_lower = clean_q.lower()
    if any(k in q_lower for k in space_keywords) or (en_q and any(k in en_q.lower() for k in space_keywords)):
        for term in search_terms:
            for it in search_nasa_video(term, limit=3):
                u = str(it.get("url") or "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    candidates.append(it)

    # 2. 檢索 YouTube 歷史紀錄片與實拍影片 (yt-dlp ytsearch)
    for term in search_terms[:2]:
        for it in search_youtube_video(term, limit=3):
            u = str(it.get("url") or "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                candidates.append(it)
        if len(candidates) >= limit:
            break

    # 3. 檢索 Wikimedia Commons 真實歷史/科學影片
    for term in search_terms:
        for it in search_wikimedia_video(term, limit=3):
            u = str(it.get("url") or "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                candidates.append(it)

    # 4. 檢索 Internet Archive (archive.org) 歷史新聞片與紀錄片
    for term in search_terms:
        if len(candidates) >= limit + 2:
            break
        for it in search_internet_archive_video(term, limit=2):
            u = str(it.get("url") or "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                candidates.append(it)

    candidates.sort(key=lambda c: score_candidate_image(c, clean_q, en_q), reverse=True)
    return candidates[:limit]


def should_prefer_archival_video(query: str | None, narration: str = "") -> bool:
    """
    AI 依敘述與檢索詞自動判斷本幕是否應優先抓取「真實考據影片（動態 B-Roll）」：
    - 若涉及靜態契約、藍圖、文件、肖像、地圖、硬幣/標誌 -> 優先抓靜態照片 (False)
    - 若涉及動態事件、發射、航行、演說、簽署現場、街頭活動、實驗運作、戰爭演習、工業產線 -> 優先抓影片 (True)
    """
    if not query:
        return False

    q_lower = query.lower()
    narr_lower = (narration or "").lower()

    # 明確屬於靜態紙本/肖像/圖表的關鍵詞 -> 維持抓照片
    static_keywords = (
        "blueprint", "contract", "document", "portrait", "map", "diagram", "chart",
        "letter", "patent", "logo", "coin", "stamp", "newspaper", "headline", "book",
        "藍圖", "合約", "契約", "文件", "肖像", "地圖", "圖表", "信件", "專利", "報紙", "頭版",
    )
    if any(k in q_lower for k in static_keywords) and not any(w in narr_lower for w in ("儀式", "現場", "演說", "發射")):
        return False

    # 明確具有動態感、歷史現場或運作過程的關鍵詞 -> 優先抓影片
    dynamic_query_keywords = (
        "launch", "flight", "sailing", "submarine", "fleet", "navy", "speech", "summit",
        "ceremony", "exhibition", "street", "protest", "parade", "collapse", "fall",
        "test", "experiment", "factory", "production", "assembly", "orbit", "landing",
        "footage", "newsreel", "video", "archive", "walking", "moving", "explosion",
    )
    dynamic_narr_keywords = (
        "發射", "升空", "航行", "潛航", "艦隊", "演說", "演講", "致詞", "展覽會", "街頭",
        "遊行", "排隊", "湧入", "倒塌", "解體", "實驗", "測試", "運轉", "生產線", "工廠",
        "登陸", "著陸", "觀測", "移動", "滑行", "呼嘯", "駛入", "簽署儀式", "畫面", "鏡頭",
    )
    if any(k in q_lower for k in dynamic_query_keywords) or any(k in narr_lower for k in dynamic_narr_keywords):
        return True

    return False


def search_multi_source_image(query: str) -> dict[str, object] | None:
    """自動為 Auto-PiP 挑選最佳匹配的真實考據照片（級聯多來源聚合）。"""
    cands = search_all_source_candidates(query, limit=6)
    return cands[0] if cands else None


def _pip_cfg(scfg: dict) -> dict:
    pip = scfg.get("pip")
    return pip if isinstance(pip, dict) else {}


def pip_switch_on(pip_cfg: object) -> bool:
    """右邊抽屜「啟用本幕考據」。沒寫或關掉就是關，自動下載不得把它打開。"""
    return isinstance(pip_cfg, dict) and bool(pip_cfg.get("enabled", False))


def read_scene_pip_query(scene_dir: Path) -> str | None:
    """只讀建案時寫入的考據詞，不再現場補判。"""
    s_yaml_p = scene_dir / "scene.yaml"
    if not s_yaml_p.is_file():
        return None
    try:
        scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    q = str(_pip_cfg(scfg).get("query") or "").strip()
    return q or None


def _download_image_bytes(img_url: str, fallback_url: str | None = None) -> bytes | None:
    urls_to_try = [u for u in [img_url, fallback_url] if u and str(u).strip()]
    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    for target_u in urls_to_try:
        is_wiki = "wikimedia.org" in target_u.lower() or "wikipedia.org" in target_u.lower()
        req_headers = WIKIMEDIA_HEADERS if is_wiki else browser_headers
        for attempt in range(1, 3):
            try:
                r = requests.get(target_u, headers=req_headers, timeout=15)
                if r.status_code == 429 and attempt < 2:
                    time.sleep(2.0)
                    continue
                if r.status_code == 200 and r.content and len(r.content) > 800:
                    return r.content
                print(f"[warn] 考據圖下載 HTTP {r.status_code}：{target_u}")
            except Exception as exc:
                print(f"[warn] 考據圖下載失敗（第 {attempt} 次）：{exc}")
                if attempt < 2:
                    time.sleep(1.0)
    return None


def mark_scene_pip_error(
    scene_dir: Path,
    message: str,
    query: str | None = None,
    rejected_candidates: list[dict[str, object]] | None = None,
) -> None:
    """把考據失敗原因與抓到但未通過的候選清單寫進該幕 scene.yaml，供分鏡卡片與抽屜顯示。"""
    s_yaml_p = scene_dir / "scene.yaml"
    if not s_yaml_p.is_file():
        return
    try:
        scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
    except Exception:
        return
    prev = _pip_cfg(scfg)
    q = (query or prev.get("query") or "").strip()
    next_pip = {
        **prev,
        "enabled": False,
        "query": q or prev.get("query"),
        "fetch_error": str(message).strip()[:300],
    }
    if rejected_candidates is not None:
        next_pip["rejected_candidates"] = rejected_candidates
    scfg["pip"] = next_pip
    s_yaml_p.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_pip_yaml(scene_dir: Path, scfg: dict, query: str, result: dict[str, object], enabled: bool) -> None:
    s_yaml_p = scene_dir / "scene.yaml"
    prev = _pip_cfg(scfg)
    is_video = str(result.get("media_type") or prev.get("media_type") or "image").lower() == "video"
    # 只要是考據影片，一律作為全螢幕 B-Roll (mode="broll" / spotlight 家族) 取代或覆蓋該幕背景圖
    if is_video:
        chosen_mode = "broll"
    else:
        chosen_mode = prev.get("mode") or infer_pip_mode(query, str(scfg.get("narration", "")))
        if chosen_mode == "broll":
            chosen_mode = infer_pip_mode(query, str(scfg.get("narration", "")))

    rej_png = scene_dir / "pip_rejected.png"
    if rej_png.is_file():
        try:
            rej_png.unlink()
        except Exception:
            pass

    scfg["pip"] = {
        "enabled": enabled,
        "media_type": "video" if is_video else "image",
        "image": "pip.png",
        "video": "pip.mp4" if is_video else None,
        "position": prev.get("position", "right-center"),
        "mode": chosen_mode,
        "scale": prev.get("scale", 0.24),
        "border": prev.get("border", 5),
        "query": query,
        "source_title": result.get("title", "") if result else prev.get("source_title", ""),
        "source_url": result.get("url", "") if result else prev.get("source_url", ""),
        "verified": bool(result.get("verified", False)),
        "review_reason": str(result.get("review_reason") or ""),
    }
    scfg["pip"].pop("fetch_error", None)
    scfg["pip"].pop("rejected_candidates", None)
    s_yaml_p.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def ensure_scene_pip_query(scene_dir: Path) -> str | None:
    """讀取既有考據檢索詞；沒有的話依本幕旁白補判一次。"""
    s_yaml_p = scene_dir / "scene.yaml"
    if not s_yaml_p.is_file():
        return None
    scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
    q = str(_pip_cfg(scfg).get("query") or "").strip()
    if q:
        return q

    narration = str(scfg.get("narration") or "").strip()
    if not narration:
        return None

    try:
        from aivideo.story_generator import batch_detect_pip_plans

        detected = batch_detect_pip_plans([narration])
        plan = detected[0] if detected and isinstance(detected[0], dict) else None
        q = str(plan.get("query") or "").strip() if plan else ""
        ai_mode = str(plan.get("mode") or "").strip() if plan else ""
        ai_mtype = str(plan.get("media_type") or "").strip() if plan else ""
    except Exception as exc:
        print(f"[warn] 【{scene_dir.name}】補判考據詞失敗: {exc}")
        q = ""
        ai_mode = ""
        ai_mtype = ""

    if not q:
        return None

    prev = _pip_cfg(scfg)
    chosen_mode = prev.get("mode") or ai_mode or infer_pip_mode(q, narration)
    chosen_mtype = prev.get("media_type") or ai_mtype or ("video" if chosen_mode == "broll" else "image")
    scfg["pip"] = {
        **prev,
        "enabled": bool(prev.get("enabled", False)),
        "media_type": chosen_mtype,
        "image": prev.get("image", "pip.png"),
        "position": prev.get("position", "right-center"),
        "mode": chosen_mode,
        "scale": prev.get("scale", 0.24),
        "border": prev.get("border", 5),
        "query": q,
    }
    s_yaml_p.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"[info] 【{scene_dir.name}】補上考據檢索詞：{q}")
    return q


def backfill_missing_pip_queries(job_dir: Path) -> int:
    """一鍵全流程開始前，為尚無 query 的分鏡一次補上考據詞（不覆蓋已有的）。"""
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return 0

    missing: list[Path] = []
    for s_dir in sorted(p for p in scenes_dir.iterdir() if p.is_dir()):
        s_yaml_p = s_dir / "scene.yaml"
        if not s_yaml_p.is_file() or (s_dir / "pip.png").is_file():
            continue
        scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
        if not str(_pip_cfg(scfg).get("query") or "").strip():
            missing.append(s_dir)

    if not missing:
        return 0

    detected = auto_detect_scene_reference_entities(job_dir)
    filled = 0
    for s_dir in missing:
        q = detected.get(s_dir.name)
        if not q:
            continue
        s_yaml_p = s_dir / "scene.yaml"
        scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
        prev = _pip_cfg(scfg)
        # 這一幕原本沒有開關，代表是這次自動挑中的，打開。使用者已關掉的維持關掉。
        prev_enabled = prev.get("enabled") if "enabled" in prev else None
        scfg["pip"] = {
            **prev,
            "enabled": True if prev_enabled is None else bool(prev_enabled),
            "image": prev.get("image", "pip.png"),
            "position": prev.get("position", "right-center"),
            "mode": prev.get("mode") or infer_pip_mode(q, str(scfg.get("narration", ""))),
            "scale": prev.get("scale", 0.24),
            "border": prev.get("border", 5),
            "query": q,
        }
        s_yaml_p.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        filled += 1
    if filled:
        print(f"[info] 已為 {filled} 場尚無考據詞的分鏡補上檢索詞")
    return filled


def infer_pip_mode(query: str | None, narration: str = "") -> str:
    """
    AI 智能決策判定器：自動判定考據圖應採用「黑底歷史聚焦 (spotlight)」還是「畫中畫小卡 (pip)」：
    - 歷史重大轉折、協議簽字、震撼名場面、世界地圖、政權解體：自動判為 spotlight（黑底慢推浮現）
    - 人物肖像、裝備載具、建築工廠、貨幣或一般物品：自動判為 pip（右半部置中畫中畫）
    """
    if not query:
        return "pip"

    q_lower = query.lower()
    narr_lower = narration.lower()

    # 關鍵名場面與歷史轉折特徵詞
    spotlight_query_keywords = (
        "signing", "agreement", "treaty", "summit", "exhibition", "collapse",
        "fall", "revolution", "protest", "crisis", "map", "document", "historic",
        "cold war", "iron curtain", "drinking pepsi photo", "famous photo", "ceremony",
    )
    spotlight_narr_keywords = (
        "簽約", "協議", "合約", "簽署", "展覽會", "解體", "倒塌", "冷戰", "鐵幕",
        "歷史性的", "名場面", "震撼", "反轉", "條約", "宣言", "地圖", "合影", "照片",
    )

    if any(k in q_lower for k in spotlight_query_keywords) or any(k in narr_lower for k in spotlight_narr_keywords):
        return "spotlight"

    return "pip"


def _extract_video_clip_and_frames(
    video_url: str,
    out_mp4: Path,
    out_png: Path,
    max_duration: float = 16.0,
) -> list[bytes]:
    """
    從遠端或本地影片網址擷取前段高畫質無音軌 B-Roll 片段 (out_mp4)，
    並抽取 3 張不同時間點的關鍵影格 (JPEG bytes) 供 Gemini 多模態敘述符合度審查，
    同時輸出第一張清晰影格為 out_png 作為預覽縮圖。
    """
    with tempfile.TemporaryDirectory(prefix="aivideo_pip_vid_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        raw_input = tmp_dir / "raw_input.mp4"

        clean_u = video_url.strip()
        is_direct_media = any(
            clean_u.lower().split("?")[0].endswith(ext)
            for ext in (".mp4", ".webm", ".ogv", ".ogg", ".mov", ".mkv")
        )

        # 1. 下載或透過 yt-dlp / requests 取得影片前段至暫存檔
        downloaded = False
        if not is_direct_media and shutil.which("yt-dlp"):
            try:
                out_tpl = str(tmp_dir / "raw_input.%(ext)s")
                cmd_yt = [
                    "yt-dlp",
                    "--no-playlist",
                    "--no-warnings",
                    "-f", "mp4[height<=1080]/best[height<=1080]/best",
                    "--download-sections", f"*0-{int(max_duration + 4)}",
                    "-o", out_tpl,
                    clean_u,
                ]
                proc = subprocess.run(cmd_yt, capture_output=True, text=True, timeout=40)
                if proc.returncode == 0:
                    for dl_f in tmp_dir.glob("raw_input.*"):
                        if dl_f.is_file() and dl_f.stat().st_size > 10_000:
                            raw_input = dl_f
                            downloaded = True
                            break
            except Exception:
                pass

        if not downloaded:
            try:
                with requests.get(clean_u, headers=WIKIMEDIA_HEADERS, stream=True, timeout=20) as r:
                    if r.status_code == 200:
                        max_bytes = 45 * 1024 * 1024  # 最多讀取 45MB 避免超大型檔案卡住
                        written = 0
                        with open(raw_input, "wb") as f:
                            for chunk in r.iter_content(chunk_size=256 * 1024):
                                if not chunk:
                                    break
                                f.write(chunk)
                                written += len(chunk)
                                if written >= max_bytes:
                                    break
                        if written > 10_000:
                            downloaded = True
            except Exception as exc:
                print(f"[warn] 考據影片串流下載失敗：{exc}")

        src_target = str(raw_input) if downloaded else clean_u

        # 2. 用 ffprobe 探測影片長度，挑選略過片頭黑畫面後的精華區間
        vid_dur = 8.0
        try:
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    src_target,
                ],
                capture_output=True,
                text=True,
                timeout=12,
            )
            d_val = float((probe.stdout or "").strip())
            if d_val > 0.5:
                vid_dur = d_val
        except Exception:
            pass

        # 若影片較長（如新聞片含片頭字卡），自動略過前 1.5~3 秒片頭
        start_sec = 2.0 if vid_dur > 10.0 else (0.5 if vid_dur > 3.0 else 0.0)
        clip_dur = min(max_duration, max(2.0, vid_dur - start_sec))

        # 3. 轉碼產生標準無聲 16:9 1080p B-Roll MP4
        norm_mp4 = tmp_dir / "norm.mp4"
        vf_scale = (
            "scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,setsar=1"
        )
        cmd_norm = [
            "ffmpeg", "-y",
            "-ss", f"{start_sec:.2f}",
            "-i", src_target,
            "-t", f"{clip_dur:.2f}",
            "-an",
            "-vf", vf_scale,
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(norm_mp4),
        ]
        proc_norm = subprocess.run(cmd_norm, capture_output=True, text=True, timeout=35)
        if proc_norm.returncode != 0 or not norm_mp4.is_file() or norm_mp4.stat().st_size < 5_000:
            return []

        # 4. 從轉碼後的片段抽取 3 張代表影格（15%、50%、85%）供 AI 審查
        frames_bytes: list[bytes] = []
        sample_points = [
            max(0.1, clip_dur * 0.15),
            max(0.3, clip_dur * 0.50),
            max(0.5, clip_dur * 0.82),
        ]
        for idx_f, t_sec in enumerate(sample_points):
            frame_jpg = tmp_dir / f"frame_{idx_f}.jpg"
            cmd_f = [
                "ffmpeg", "-y",
                "-ss", f"{t_sec:.2f}",
                "-i", str(norm_mp4),
                "-frames:v", "1",
                "-q:v", "3",
                str(frame_jpg),
            ]
            subprocess.run(cmd_f, capture_output=True, text=True, timeout=10)
            if frame_jpg.is_file() and frame_jpg.stat().st_size > 1_000:
                frames_bytes.append(frame_jpg.read_bytes())

        if not frames_bytes:
            return []

        # 暫存複製到目標路徑（若審查未過會由呼叫端清理或覆蓋）
        shutil.copyfile(norm_mp4, out_mp4)
        try:
            # 用中段或首張清晰影格存為 pip.png 縮圖
            chosen_thumb = frames_bytes[min(1, len(frames_bytes) - 1)]
            img = Image.open(io.BytesIO(chosen_thumb)).convert("RGBA")
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            img.save(out_png, "PNG")
        except Exception:
            pass

        return frames_bytes


def verify_pip_match_with_ai(
    narration: str,
    query: str,
    candidate_title: str = "",
    candidate_url: str = "",
    image_bytes: bytes | None = None,
    frame_bytes_list: list[bytes] | None = None,
    media_type: str = "image",
) -> dict[str, Any]:
    """
    呼叫 Gemini AI (優先使用 gemini-3.8-flash / gemini-3.7-flash) 進行多模態視覺考據審查裁判：
    嚴格檢驗此候選照片或影片（多張關鍵影格）與圖片真實檔名是否真正吻合口白台詞的情境與實體。
    - 若吻合且合理 -> passed: True
    - 若主題歪樓、人物不符（如檔名為其他無關名人）、概念不符或審核連線異常 -> passed: False（嚴格把關，絕不預設放行）
    """
    clean_narr = (narration or "").strip()
    if not clean_narr:
        return {"passed": False, "confidence": 0.0, "reason": "無口白可供核對"}

    is_video = media_type == "video" or bool(frame_bytes_list)
    media_label = "archival video clip (represented by sequential keyframes)" if is_video else "real-world photograph"

    url_filename = ""
    if candidate_url:
        try:
            url_filename = urllib.parse.unquote(candidate_url.split("?")[0].rstrip("/").split("/")[-1])
        except Exception:
            url_filename = candidate_url

    prompt = f"""You are a strict documentary film fact-checker and visual verification editor.
A scene has the following Chinese voiceover narration:
"{clean_narr}"

The researcher queried: "{query}"
Candidate {media_label} page/source title: "{candidate_title}"
Candidate file name from URL: "{url_filename}"

VERIFICATION TASK:
Determine if this {media_label} is factually and contextually SUITABLE to show as authentic documentary visual evidence during this exact narration.

STRICT CRITERIA:
1. IDENTITY & ENTITY MATCH:
   - If the narration/query is about a specific historical person, scientist, chef, or leader, the image MUST actually depict that exact person (or their authentic work/restaurant/invention).
   - Check the URL file name ("{url_filename}") and page title ("{candidate_title}") carefully: if the file name shows a completely different person (e.g. a pop singer or unrelated celebrity from a 'List of people...' page), IMMEDIATELY REJECT (`passed: false`)!
2. REJECT (`passed = false`) IF:
   - Wrong person, wrong vehicle/product, or topic drift (e.g., a generic list article, unrelated battle, map, coat of arms, or random icon).
   - Pure text title cards, blank/corrupted frames, unrelated talking-head studio interviews, video game footage, or memes.
   - The visual content contradicts or is unrelated to the core subject of the voiceover.
3. APPROVE (`passed = true`) ONLY IF:
   - It genuinely shows the actual historical figure, signed document, vehicle/ship, facility, spacecraft/experiment, or authentic historical/archival scene described.

Return ONLY a valid JSON object:
{{
  "passed": true / false,
  "confidence": 0.0 to 1.0,
  "reason": "簡短繁體中文說明吻合或不合原因 (繁體中文，限35字內)"
}}
"""
    try:
        from aivideo.commands.check import _load_dotenv
        _load_dotenv()
        from google import genai
        from google.genai import types

        contents: list[Any] = [prompt]
        raw_images = frame_bytes_list if frame_bytes_list else ([image_bytes] if image_bytes else [])
        for b_data in raw_images[:3]:
            if not b_data:
                continue
            try:
                img_io = io.BytesIO(b_data)
                pil_img = Image.open(img_io).convert("RGB")
                pil_img.thumbnail((512, 512), Image.Resampling.LANCZOS)
                thumb_io = io.BytesIO()
                pil_img.save(thumb_io, format="JPEG", quality=80)
                thumb_bytes = thumb_io.getvalue()
                contents.append(types.Part.from_bytes(data=thumb_bytes, mime_type="image/jpeg"))
            except Exception:
                pass

        last_err = None
        for model_name in VISION_REVIEW_MODELS:
            try:
                client = genai.Client(**get_gemini_client_kwargs(model=model_name))
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
                if resp.text:
                    parsed = json.loads(resp.text)
                    passed = bool(parsed.get("passed", False))
                    conf = float(parsed.get("confidence", 0.0))
                    reason = str(parsed.get("reason", "")).strip()
                    return {
                        "passed": passed and (conf >= 0.55),
                        "confidence": conf,
                        "reason": reason,
                    }
            except Exception as model_err:
                last_err = model_err
                continue

        print(f"[warn] AI 考據審查所有候選模型皆呼叫失敗 ({last_err})，採取嚴格拒絕策略 (Fail-Closed)")
        return {"passed": False, "confidence": 0.0, "reason": "AI 審核連線異常，安全拒絕未驗證素材"}
    except Exception as e:
        print(f"[warn] AI 考據審查例外失敗: {e}，採取嚴格拒絕策略 (Fail-Closed)")
        return {"passed": False, "confidence": 0.0, "reason": "AI 審核異常，安全拒絕未驗證素材"}


def fetch_single_scene_pip(
    scene_dir: Path,
    query: str | None = None,
    media_type: str = "auto",
) -> bool:
    """
    為單一分鏡檢索並下載真實考據素材（支援動態影片 pip.mp4 或靜態照片 pip.png）：
    - media_type="auto"：由 AI 依口白與檢索詞自動判斷是否優先抓影片；若影片無結果或未通過審查，自動退回抓考據照片。
    - media_type="video"：強制檢索考據影片並驗證關鍵影格。
    - media_type="image"：僅檢索考據照片。
    所有候選皆須通過 Gemini AI 視覺與口白敘述吻合度審查才啟用；若失敗則保存退件候選與縮圖供介面檢視。
    """
    s_yaml_p = scene_dir / "scene.yaml"
    if not s_yaml_p.is_file():
        return False

    scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
    q = str(query or _pip_cfg(scfg).get("query") or "").strip()
    if not q:
        print(f"[skip] 【{scene_dir.name}】本幕無需考據素材")
        return False

    narration = str(scfg.get("narration") or "")
    last_err = None
    rejected_items: list[dict[str, object]] = []
    saved_rejected_preview = False
    rej_png_path = scene_dir / "pip_rejected.png"

    pip_cfg = _pip_cfg(scfg)
    cfg_mtype = str(pip_cfg.get("media_type") or "").strip().lower()
    cfg_mode = str(pip_cfg.get("mode") or "").strip().lower()

    # 優先依照 AI 於建案/切鏡時寫入 scene.yaml 的 media_type / mode 決定抓影片或照片；
    # 若為未標記 media_type 的舊分鏡才退回 should_prefer_archival_video 判斷
    if media_type == "video":
        want_video_first = True
    elif media_type == "image":
        want_video_first = False
    elif cfg_mtype == "video" or cfg_mode == "broll":
        want_video_first = True
    elif cfg_mtype == "image" and cfg_mode in ("pip", "spotlight"):
        want_video_first = False
    else:
        want_video_first = should_prefer_archival_video(q, narration)

    # ==========================================================
    # 階段 A：優先嘗試檢索並驗證「真實考據影片 (pip.mp4)」
    # ==========================================================
    if want_video_first:
        vid_candidates = search_all_source_video_candidates(q, limit=5)
        if vid_candidates:
            print(f"[info] 【{scene_dir.name}】偵測為動態考據需求，優先審核 {len(vid_candidates)} 部候選影片：{q}")
        for i, v_cand in enumerate(vid_candidates, 1):
            v_url = str(v_cand.get("url") or "").strip()
            if not v_url:
                continue
            tmp_mp4 = scene_dir / "pip_candidate_tmp.mp4"
            tmp_png = scene_dir / "pip_candidate_tmp.png"
            try:
                frames = _extract_video_clip_and_frames(v_url, tmp_mp4, tmp_png)
                if not frames or not tmp_mp4.is_file():
                    last_err = f"無法擷取影片候選 {i}"
                    continue

                cand_title = str(v_cand.get("title") or q)
                review = verify_pip_match_with_ai(
                    narration=narration,
                    query=q,
                    candidate_title=cand_title,
                    candidate_url=v_url,
                    frame_bytes_list=frames,
                    media_type="video",
                )
                if not review["passed"]:
                    rej_reason = str(review.get("reason") or "影片內容與本幕口白不符").strip()
                    print(f"[review-reject] 【{scene_dir.name}】影片候選 {i} 未通過 AI 審查: {rej_reason}，改試下一部")
                    if not saved_rejected_preview and tmp_png.is_file():
                        try:
                            shutil.copyfile(str(tmp_png), str(rej_png_path))
                            saved_rejected_preview = True
                        except Exception:
                            pass
                    rejected_items.append(
                        {
                            "title": cand_title,
                            "url": v_url,
                            "thumbnail_url": str(v_cand.get("thumbnail_url") or "") or None,
                            "source": str(v_cand.get("source") or "全網考據影片"),
                            "media_type": "video",
                            "reason": rej_reason,
                        }
                    )
                    last_err = f"有抓到影片但 AI 判定不符：{rej_reason}"
                    continue

                # 通過審查！正式啟用 pip.mp4 與代表縮圖 pip.png
                shutil.move(str(tmp_mp4), str(scene_dir / "pip.mp4"))
                if tmp_png.is_file():
                    shutil.move(str(tmp_png), str(scene_dir / "pip.png"))
                result = {
                    **v_cand,
                    "url": v_url,
                    "media_type": "video",
                    "verified": True,
                    "review_reason": review["reason"],
                }
                _write_pip_yaml(scene_dir, scfg, q, result, enabled=True)
                print(f"[ok]   【{scene_dir.name}】🎬 通過 AI 多影格審核並套用全螢幕考據影片：{q} ({review['reason']})")
                return True
            except Exception as e:
                last_err = e
                print(f"[warn] 【{scene_dir.name}】影片候選 {i} 處理失敗: {e}")
            finally:
                for p_tmp in (tmp_mp4, tmp_png):
                    if p_tmp.is_file():
                        try:
                            p_tmp.unlink()
                        except Exception:
                            pass

        if media_type == "video":
            err_msg = str(last_err) if last_err else f"沒抓到影片：搜尋「{q}」無相符影片結果"
            mark_scene_pip_error(scene_dir, err_msg, q, rejected_candidates=rejected_items[:4])
            return False
        print(f"[info] 【{scene_dir.name}】未找到合適考據影片，自動退回檢索真實考據照片：{q}")

    # ==========================================================
    # 階段 B：檢索並驗證「真實考據照片 (pip.png)」
    # ==========================================================
    candidates = search_all_source_candidates(q, limit=6)
    if not candidates:
        print(f"[skip] 【{scene_dir.name}】未檢索到合適考據照片：{q}")
        err_msg = str(last_err) if rejected_items else f"沒抓到圖/影片：搜尋「{q}」無相符結果"
        mark_scene_pip_error(scene_dir, err_msg, q, rejected_candidates=rejected_items[:4])
        return False

    downloaded_any = False
    for i, result in enumerate(candidates, 1):
        raw_url = str(result.get("url", "")).strip()
        thumb_url = str(result.get("thumbnail_url") or "").strip() or None
        img_url = raw_url
        if not img_url:
            continue
        try:
            content = _download_image_bytes(img_url)
            if not content and thumb_url and thumb_url != img_url:
                content = _download_image_bytes(thumb_url)
            if not content:
                last_err = f"無法下載候選圖片 {i}"
                continue
            downloaded_any = True

            cand_title = str(result.get("title") or q)
            # 關鍵審查關卡：透過 AI 比對口白、檔名與圖片內容是否吻合
            review = verify_pip_match_with_ai(
                narration=narration,
                query=q,
                candidate_title=cand_title,
                candidate_url=img_url,
                image_bytes=content,
                media_type="image",
            )

            if not review["passed"]:
                rej_reason = str(review.get("reason") or "圖片內容與本幕口白不符").strip()
                print(f"[review-reject] 【{scene_dir.name}】候選 {i} 未通過 AI 審查: {rej_reason}，改試下一張")
                if not saved_rejected_preview:
                    try:
                        rej_img = Image.open(io.BytesIO(content)).convert("RGBA")
                        rej_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                        rej_img.save(rej_png_path, "PNG")
                        saved_rejected_preview = True
                    except Exception:
                        pass
                rejected_items.append(
                    {
                        "title": cand_title,
                        "url": img_url,
                        "thumbnail_url": str(result.get("thumbnail_url") or img_url),
                        "source": str(result.get("source") or "全網歷史圖庫"),
                        "media_type": "image",
                        "reason": rej_reason,
                    }
                )
                last_err = f"有抓到圖但 AI 判定不符：{rej_reason}"
                continue

            # 通過審核！若先前殘留 pip.mp4 則清除，正式縮圖存檔並啟用
            old_mp4 = scene_dir / "pip.mp4"
            if old_mp4.is_file():
                try:
                    old_mp4.unlink()
                except Exception:
                    pass

            img = Image.open(io.BytesIO(content)).convert("RGBA")
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            img.save(scene_dir / "pip.png", "PNG")
            result = {
                **result,
                "url": img_url,
                "media_type": "image",
                "verified": True,
                "review_reason": review["reason"],
            }
            _write_pip_yaml(scene_dir, scfg, q, result, enabled=True)
            print(f"[ok]   【{scene_dir.name}】通過 AI 審核並套用考據圖：{q} ({review['reason']})")
            return True
        except Exception as e:
            last_err = e
            print(f"[warn] 【{scene_dir.name}】候選 {i}/{len(candidates)} 失敗: {e}，改試下一張")
            continue

    # 若所有候選皆未通過 AI 吻合度審核，保存退件紀錄並自動降級為純 AI 生成畫面
    if rejected_items:
        first_rej = rejected_items[0]
        final_err = f"有抓到{'影片' if first_rej.get('media_type') == 'video' else '圖'}但 AI 判定不符：{first_rej.get('reason')}（候選：{first_rej.get('title')}）"
    elif not downloaded_any:
        final_err = f"有搜到 {len(candidates)} 筆候選但無法下載圖檔（檢索詞：{q}）"
    else:
        final_err = f"考據檢索失敗：{last_err}"

    print(f"[fallback] 【{scene_dir.name}】{final_err}")
    mark_scene_pip_error(scene_dir, final_err, q, rejected_candidates=rejected_items[:4])
    return False


def auto_detect_scene_reference_entities(job_dir: Path) -> dict[str, str]:
    """呼叫 Gemini 掃描該 Job 所有分鏡台詞，結合主題背景，智能判定哪些幕需要真實歷史/設備/生物參考圖，並輸出檢索詞。"""
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return {}

    topic = ""
    subject_anchor = ""
    try:
        from aivideo.job_files import load_job_config

        jcfg = load_job_config(job_dir)
        topic = str(jcfg.get("title") or jcfg.get("topic") or "")
        subject_anchor = str((jcfg.get("visual_anchors") or {}).get("subject") or "")
    except Exception:
        pass

    scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])
    scene_inputs = []
    for s_dir in scene_folders:
        s_yaml_p = s_dir / "scene.yaml"
        if not s_yaml_p.is_file():
            continue
        try:
            with open(s_yaml_p, "r", encoding="utf-8") as yf:
                scfg = yaml.safe_load(yf) or {}
            narration = scfg.get("narration", "").strip()
            if narration:
                scene_inputs.append({
                    "id": s_dir.name,
                    "narration": narration,
                })
        except Exception:
            pass

    if not scene_inputs:
        return {}

    _load_dotenv()
    from google import genai
    from google.genai import types

    context_lines = []
    if topic:
        context_lines.append(f"- Documentary Core Topic: {topic}")
    if subject_anchor:
        context_lines.append(f"- Core Subject Anchor & Era: {subject_anchor}")
    context_block = f"\nDOCUMENTARY CONTEXT:\n" + "\n".join(context_lines) + "\n" if context_lines else ""

    prompt = f"""You are an archival visual researcher and documentary film archivist.
Analyze the following scene narrations for a documentary video.{context_block}
Identify scenes that mention or describe a SPECIFIC REAL-WORLD entity, historical person, actual scientific instrument/telescope/satellite, historical event, organism/species, blueprint, or document where displaying a REAL archival photograph, blueprint, or factual diagram (as a Picture-in-Picture card) would strongly enhance documentary credibility.

Scenes:
{json.dumps(scene_inputs, ensure_ascii=False, indent=2)}

INSTRUCTIONS & PRIORITY:
1. FOCUS ON AUTHENTIC ARCHIVAL EVIDENCE:
   - Priority 1: Genuine Historical Documents / Contracts / Blueprints / News Clippings (e.g., "Pepsi USSR barter trade agreement 1989", "Apollo 11 flight plan NASA", "Perkin-Elmer mirror polish blueprint").
   - Priority 2: Key Historical Figures / Decision Makers: Full official name with title or era (e.g., "Donald Kendall Pepsi CEO", "Mikhail Gorbachev portrait", "Burn-Jeng Lin TSMC").
   - Priority 3: Specific Vehicles / Ships / Spacecraft / Weapons: Exact official model, class, or NATO reporting name (e.g., "Project 613 Whiskey-class submarine", "Lockheed U-2 spy plane").
   - Priority 4: Specific Instruments / Technology / Facilities: Concrete device or facility (e.g., "Hubble primary mirror", "ASML Twinscan immersion lithography").
2. FORBIDDEN ABSTRACT TERMS:
   - Do NOT output abstract emotions, philosophical concepts, or generic topics (e.g., "Cold War diplomacy", "secret trade", "military tension"). Return null for these.
3. COVERAGE & SELECTIVITY:
   - Aim for 45%~70% of scenes to have real archival reference cards whenever concrete real-world entities, locations, institutions, historical moments, or artifacts are mentioned.

OUTPUT FORMAT:
Return a JSON object mapping scene_id to the search query string (or null):
{{
  "001_scene_1": "search query or null",
  "002_scene_2": null
}}
"""

    for model_name in TEXT_MODELS:
        try:
            client = genai.Client(**get_gemini_client_kwargs(model=model_name))
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
                if isinstance(parsed, dict):
                    return {k: str(v).strip() for k, v in parsed.items() if v and str(v).strip().lower() != "null"}
        except Exception:
            continue

    return {}


def auto_fetch_and_apply_pip(job_dir: Path, progress_callback=None, check_control=None) -> int:
    """自動為指定專案檢索並套用真實參考圖 (Auto-PiP)。優先使用建案時預先判斷的檢索詞，無須重複分析。"""
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return 0

    if check_control and check_control(phase="考據"):
        return 0

    scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()])
    if not scene_folders:
        return 0

    # 1. 只抓右邊開關還開著、而且已有考據詞的幕。關掉的幕留著詞，但不下載、不重新打開。
    has_any_query = False
    entity_map = {}
    for s_dir in scene_folders:
        s_yaml_p = s_dir / "scene.yaml"
        if s_yaml_p.is_file():
            try:
                scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
                pip = _pip_cfg(scfg)
                q = str(pip.get("query") or "").strip()
                if q:
                    has_any_query = True
                if q and pip_switch_on(pip):
                    entity_map[s_dir.name] = q
            except Exception:
                pass

    # 2. 全片都沒有考據詞（舊專案）才補判一次。已經有詞的片子不再逐幕加詞，避免碰到使用者關掉的幕。
    if not has_any_query:
        if progress_callback:
            progress_callback(0, 1, "正在以 AI 檢索全片口白實體名詞與考據需求...")
        backfill_missing_pip_queries(job_dir)
        for s_dir in scene_folders:
            s_yaml_p = s_dir / "scene.yaml"
            if not s_yaml_p.is_file():
                continue
            scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
            pip = _pip_cfg(scfg)
            q = str(pip.get("query") or "").strip()
            if q and pip_switch_on(pip):
                entity_map[s_dir.name] = q

    if not entity_map:
        if progress_callback:
            progress_callback(1, 1, "本專案未檢測到需引用真實考據圖片的場景")
        return 0

    total_matched = len(entity_map)
    applied_count = 0

    for idx, (s_id, query) in enumerate(entity_map.items(), 1):
        s_dir = scenes_dir / s_id
        if not s_dir.is_dir():
            continue

        if check_control and check_control(phase="考據", s_dir=s_dir):
            print(f"[stop] 收到中止指令，停止考據配圖")
            break

        if (s_dir / "pip.png").is_file():
            applied_count += 1
            if progress_callback:
                progress_callback(idx, total_matched, f"【{s_id}】已有考據圖，略過下載", s_dir=s_dir)
            continue

        if progress_callback:
            progress_callback(idx, total_matched, f"正在多來源檢索【{s_id}】：{query} ...", s_dir=s_dir)

        try:
            if fetch_single_scene_pip(s_dir, query):
                applied_count += 1
                if progress_callback:
                    progress_callback(idx, total_matched, f"✅ 已為【{s_id}】套用考據圖：{query}", s_dir=s_dir)
                time.sleep(1.0)
            else:
                if progress_callback:
                    progress_callback(idx, total_matched, f"⚠️ 【{s_id}】考據未通過或無結果，繼續下一幕", s_dir=s_dir)
        except Exception as exc:
            print(f"[warn] 【{s_id}】考據圖處理失敗: {exc}")
            mark_scene_pip_error(s_dir, str(exc), query)
            if progress_callback:
                progress_callback(idx, total_matched, f"⚠️ 【{s_id}】考據失敗，繼續下一幕", s_dir=s_dir)
            continue

    return applied_count
