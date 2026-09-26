from __future__ import annotations

import io
import json
import re
import time
import urllib.parse
from pathlib import Path
from PIL import Image
import requests
import yaml

from aivideo.commands.check import _load_dotenv
from aivideo.gemini_image import get_gemini_client_kwargs
from aivideo.story_generator import TEXT_MODELS

REPO_ROOT = Path(__file__).resolve().parents[1]

WIKIMEDIA_HEADERS = {
    "User-Agent": "AIVideoDocBot/2.0 (https://github.com/aivideo/aivideo; documentary-research@aivideo-studio.org)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}


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


def search_wikipedia_summary_image(query: str, lang: str = "en") -> dict[str, object] | None:
    """呼叫維基百科 REST API 取得條目代表圖（封面圖）。支援中、英文名詞檢索。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return None
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(clean_q)}"
    try:
        resp = requests.get(url, headers=WIKIMEDIA_HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            orig = data.get("originalimage", {})
            img_url = str(orig.get("source", "")).split("?")[0]
            if img_url:
                return {
                    "title": data.get("title", clean_q),
                    "url": img_url,
                    "source": f"維基百科條目 ({lang.upper()})",
                    "width": orig.get("width", 1024),
                    "height": orig.get("height", 768),
                    "mime": "image/jpeg",
                }
    except Exception:
        pass
    return None


def search_wikimedia_image(query: str) -> dict[str, object] | None:
    """呼叫 Wikimedia Commons API 檢索公有領域高解析度真實攝影或檔案照片。"""
    clean_q = re.sub(r'["\'\(\)\[\]]', '', query).strip()
    if not clean_q:
        return None

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": clean_q,
        "gsrnamespace": 6,  # 檔案命名空間
        "gsrlimit": 6,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "format": "json",
    }
    url = f"https://commons.wikimedia.org/w/api.php?{urllib.parse.urlencode(params)}"
    try:
        resp = requests.get(url, headers=WIKIMEDIA_HEADERS, timeout=12)
        if resp.status_code != 200:
            return None
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return None

        # 優先挑選解析度合適且為常見圖檔格式的圖片
        candidates = []
        for pid, pdata in pages.items():
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

        if candidates:
            # 優先回傳第一個最相關的合適候選者
            return candidates[0]
    except Exception:
        pass

    return None


def search_all_source_candidates(query: str, limit: int = 6) -> list[dict[str, object]]:
    """跨多個高可信來源（NASA 官方影像庫、維基共享資源、中英文維基百科代表圖）聚合檢索真實照片。"""
    candidates: list[dict[str, object]] = []
    seen_urls: set[str] = set()

    clean_q = query.strip()
    if not clean_q:
        return []

    # 1. 太空、天文、科技詞彙優先呼叫 NASA 官方圖庫
    space_keywords = {"space", "telescope", "nasa", "galaxy", "satellite", "star", "hubble", "roman", "webb", "planet", "orbit", "astronaut", "mars", "moon"}
    q_lower = clean_q.lower()
    if any(k in q_lower for k in space_keywords):
        for it in search_nasa_image(clean_q, limit=3):
            if it["url"] not in seen_urls:
                seen_urls.add(it["url"])
                candidates.append(it)

    # 2. 檢索 Wikimedia Commons
    w_img = search_wikimedia_image(clean_q)
    if w_img and w_img["url"] not in seen_urls:
        seen_urls.add(w_img["url"])
        candidates.append(w_img)

    # 3. 檢索英文維基百科條目代表圖
    en_img = search_wikipedia_summary_image(clean_q, lang="en")
    if en_img and en_img["url"] not in seen_urls:
        seen_urls.add(en_img["url"])
        candidates.append(en_img)

    # 4. 檢索中文維基百科條目代表圖（支援中文人名、公司與事件）
    zh_img = search_wikipedia_summary_image(clean_q, lang="zh")
    if zh_img and zh_img["url"] not in seen_urls:
        seen_urls.add(zh_img["url"])
        candidates.append(zh_img)

    # 5. 若候選不足，嘗試簡化詞再向 Wikimedia 擴展
    if len(candidates) < limit:
        simplified = re.sub(r'\b(diagram|concept|artist concept|illustration|blueprint|image|galaxy image)\b', '', clean_q, flags=re.I).strip()
        if simplified and simplified != clean_q:
            sim_img = search_wikimedia_image(simplified)
            if sim_img and sim_img["url"] not in seen_urls:
                seen_urls.add(sim_img["url"])
                candidates.append(sim_img)

    return candidates[:limit]


def search_multi_source_image(query: str) -> dict[str, object] | None:
    """自動為 Auto-PiP 挑選最佳匹配的真實考據照片（級聯多來源聚合）。"""
    cands = search_all_source_candidates(query, limit=6)
    return cands[0] if cands else None


def _pip_cfg(scfg: dict) -> dict:
    pip = scfg.get("pip")
    return pip if isinstance(pip, dict) else {}


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


def _download_image_bytes(img_url: str) -> bytes | None:
    for attempt in range(1, 4):
        try:
            r = requests.get(img_url, headers=WIKIMEDIA_HEADERS, timeout=20)
            if r.status_code == 429 and attempt < 3:
                time.sleep(2.0 * attempt)
                continue
            if r.status_code == 200 and r.content:
                return r.content
            print(f"[warn] 考據圖下載 HTTP {r.status_code}：{img_url}")
        except Exception as exc:
            print(f"[warn] 考據圖下載失敗（第 {attempt} 次）：{exc}")
            if attempt < 3:
                time.sleep(1.5 * attempt)
    return None


def mark_scene_pip_error(scene_dir: Path, message: str, query: str | None = None) -> None:
    """把考據失敗寫進該幕 scene.yaml，供分鏡卡片 tag 顯示。"""
    s_yaml_p = scene_dir / "scene.yaml"
    if not s_yaml_p.is_file():
        return
    try:
        scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
    except Exception:
        return
    prev = _pip_cfg(scfg)
    q = (query or prev.get("query") or "").strip()
    scfg["pip"] = {
        **prev,
        "enabled": False,
        "query": q or prev.get("query"),
        "fetch_error": str(message).strip()[:240],
    }
    s_yaml_p.write_text(yaml.safe_dump(scfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_pip_yaml(scene_dir: Path, scfg: dict, query: str, result: dict[str, object], enabled: bool) -> None:
    s_yaml_p = scene_dir / "scene.yaml"
    chosen_mode = _pip_cfg(scfg).get("mode") or infer_pip_mode(query, str(scfg.get("narration", "")))
    prev = _pip_cfg(scfg)
    scfg["pip"] = {
        "enabled": enabled,
        "image": "pip.png",
        "position": prev.get("position", "right-center"),
        "mode": chosen_mode,
        "scale": prev.get("scale", 0.24),
        "border": prev.get("border", 5),
        "query": query,
        "source_title": result.get("title", "") if result else prev.get("source_title", ""),
        "source_url": result.get("url", "") if result else prev.get("source_url", ""),
    }
    scfg["pip"].pop("fetch_error", None)
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
        from aivideo.story_generator import batch_detect_pip_queries

        detected = batch_detect_pip_queries([narration])
        q = str(detected[0]).strip() if detected and detected[0] else ""
    except Exception as exc:
        print(f"[warn] 【{scene_dir.name}】補判考據詞失敗: {exc}")
        q = ""

    if not q:
        return None

    prev = _pip_cfg(scfg)
    scfg["pip"] = {
        **prev,
        "enabled": bool(prev.get("enabled", False)),
        "image": prev.get("image", "pip.png"),
        "position": prev.get("position", "right-center"),
        "mode": prev.get("mode") or infer_pip_mode(q, narration),
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
        scfg["pip"] = {
            **prev,
            "enabled": False,
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


def fetch_single_scene_pip(scene_dir: Path, query: str | None = None) -> bool:
    """為單一分鏡檢索並下載真實考據照片 (pip.png)。多來源、多候選、下載失敗會改試下一張。"""
    s_yaml_p = scene_dir / "scene.yaml"
    if not s_yaml_p.is_file():
        return False

    scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
    q = str(query or _pip_cfg(scfg).get("query") or "").strip()
    if not q:
        print(f"[skip] 【{scene_dir.name}】本幕無需考據圖")
        return False

    candidates = search_all_source_candidates(q, limit=6)
    if not candidates:
        print(f"[skip] 【{scene_dir.name}】未檢索到合適考據照片：{q}")
        mark_scene_pip_error(scene_dir, "未找到合適照片", q)
        return False

    last_err = None
    for i, result in enumerate(candidates, 1):
        raw_url = str(result.get("url", ""))
        img_url = raw_url.split("?")[0] if raw_url else ""
        if not img_url:
            continue
        try:
            content = _download_image_bytes(img_url)
            if not content:
                last_err = f"無法下載候選 {i}"
                continue
            img = Image.open(io.BytesIO(content)).convert("RGBA")
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            img.save(scene_dir / "pip.png", "PNG")
            result = {**result, "url": img_url}
            _write_pip_yaml(scene_dir, scfg, q, result, enabled=True)
            print(f"[ok]   【{scene_dir.name}】成功下載考據圖：{q} -> {result.get('title')}")
            return True
        except Exception as e:
            last_err = e
            print(f"[warn] 【{scene_dir.name}】候選 {i}/{len(candidates)} 失敗: {e}，改試下一張")
            continue

    print(f"[skip] 【{scene_dir.name}】所有考據來源皆失敗：{q} ({last_err})")
    mark_scene_pip_error(scene_dir, f"下載失敗：{last_err}" if last_err else "所有來源皆失敗", q)
    return False


def auto_detect_scene_reference_entities(job_dir: Path) -> dict[str, str]:
    """呼叫 Gemini 掃描該 Job 所有分鏡台詞，智能判定哪些幕需要真實歷史/設備/生物參考圖，並輸出檢索詞。"""
    scenes_dir = job_dir / "scenes"
    if not scenes_dir.is_dir():
        return {}

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

    client_kwargs = get_gemini_client_kwargs()
    client = genai.Client(**client_kwargs)

    prompt = f"""You are an archival visual researcher and documentary editor.
Analyze the following scene narrations for a documentary video.
Identify scenes that mention or describe a SPECIFIC REAL-WORLD entity, historical person, actual scientific instrument/telescope/satellite, historical event, organism/species, blueprint, or document where displaying a REAL archival photograph or factual diagram (as a Picture-in-Picture card) would strongly enhance documentary credibility.

Scenes:
{json.dumps(scene_inputs, ensure_ascii=False, indent=2)}

INSTRUCTIONS:
1. For scenes that clearly describe a real-world entity, person, device, spacecraft, or document:
   Provide a concise, precise English search query suitable for Wikimedia Commons / public domain archives (e.g., "Nancy Grace Roman Space Telescope", "Hubble Space Telescope mirror", "Edward O. Wilson biologist", "Solenopsis invicta fire ant").
2. For scenes that are purely metaphorical, abstract transitions, or generic narrative where real photo is NOT needed or inappropriate:
   Set search_query to null.
3. Be selective: only 20%~45% of scenes usually need real archival reference cards to avoid visual clutter.

OUTPUT FORMAT:
Return a JSON object mapping scene_id to the search query string (or null):
{{
  "001_scene_1": "search query or null",
  "002_scene_2": null
}}
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

    # 1. 優先從各分鏡的 scene.yaml 讀取建案時已預先分析好的實體檢索詞
    entity_map = {}
    for s_dir in scene_folders:
        s_yaml_p = s_dir / "scene.yaml"
        if s_yaml_p.is_file():
            try:
                scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
                q = str(_pip_cfg(scfg).get("query") or "").strip()
                if q:
                    entity_map[s_dir.name] = q
            except Exception:
                pass

    # 2. 全片都沒有預置 query（舊專案）才補判一次；已有選擇性標註的專案不再逐幕加詞
    if not entity_map:
        if progress_callback:
            progress_callback(0, 1, "正在以 AI 檢索全片口白實體名詞與考據需求...")
        backfill_missing_pip_queries(job_dir)
        for s_dir in scene_folders:
            s_yaml_p = s_dir / "scene.yaml"
            if not s_yaml_p.is_file():
                continue
            scfg = yaml.safe_load(s_yaml_p.read_text(encoding="utf-8")) or {}
            q = str(_pip_cfg(scfg).get("query") or "").strip()
            if q:
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
                mark_scene_pip_error(s_dir, "未找到合適照片", query)
                if progress_callback:
                    progress_callback(idx, total_matched, f"⚠️ 【{s_id}】未找到考據圖，繼續下一幕", s_dir=s_dir)
        except Exception as exc:
            print(f"[warn] 【{s_id}】考據圖處理失敗: {exc}")
            mark_scene_pip_error(s_dir, str(exc), query)
            if progress_callback:
                progress_callback(idx, total_matched, f"⚠️ 【{s_id}】考據失敗，繼續下一幕", s_dir=s_dir)
            continue

    return applied_count
