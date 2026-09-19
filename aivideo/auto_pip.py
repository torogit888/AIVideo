from __future__ import annotations

import io
import json
import re
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
    cands = search_all_source_candidates(query, limit=3)
    return cands[0] if cands else None


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
                with open(s_yaml_p, "r", encoding="utf-8") as yf:
                    scfg = yaml.safe_load(yf) or {}
                q = scfg.get("pip", {}).get("query")
                if q and str(q).strip():
                    entity_map[s_dir.name] = str(q).strip()
            except Exception:
                pass

    # 2. 若分鏡尚無預置 query（例如早期專案），自動呼叫 Gemini 進行全片實體分析
    if not entity_map:
        if progress_callback:
            progress_callback(0, 1, "正在以 AI 檢索全片口白實體名詞與考據需求...")
        entity_map = auto_detect_scene_reference_entities(job_dir)

    if not entity_map:
        if progress_callback:
            progress_callback(1, 1, "本專案未檢測到需引用真實考據圖片的場景")
        return 0

    total_matched = len(entity_map)
    applied_count = 0

    from PIL import Image
    import io

    for idx, (s_id, query) in enumerate(entity_map.items(), 1):
        s_dir = scenes_dir / s_id
        if not s_dir.is_dir():
            continue

        if check_control and check_control(phase="考據", s_dir=s_dir):
            print(f"[stop] 收到中止指令，停止考據配圖")
            break

        s_yaml_p = s_dir / "scene.yaml"
        if not s_yaml_p.is_file():
            continue

        if progress_callback:
            progress_callback(idx, total_matched, f"正在多來源檢索【{s_id}】：{query} ...", s_dir=s_dir)

        # 跨來源智慧檢索真實考據圖 (NASA 官方庫、維基共享資源、維基百科中英條目)
        result = search_multi_source_image(query)
        if not result:
            print(f"[skip] 【{s_id}】多來源未匹配到合適真實照片：{query}")
            continue

        raw_url = str(result.get("url", ""))
        img_url = raw_url.split("?")[0] if raw_url else ""
        if not img_url:
            continue

        try:
            r = None
            for dl_attempt in range(1, 4):
                r = requests.get(img_url, headers=WIKIMEDIA_HEADERS, timeout=20)
                if r.status_code == 429 and dl_attempt < 3:
                    import time
                    time.sleep(2.0 * dl_attempt)
                    continue
                break

            if r is None or r.status_code != 200:
                code = r.status_code if r is not None else "None"
                print(f"[warn] 【{s_id}】圖片下載失敗 HTTP {code}：{img_url}")
                continue

            pip_p = s_dir / "pip.png"
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            img.save(pip_p, "PNG")

            # 更新 scene.yaml
            with open(s_yaml_p, "r", encoding="utf-8") as yf:
                scfg = yaml.safe_load(yf) or {}

            scfg["pip"] = {
                "enabled": True,
                "image": "pip.png",
                "position": "top-right",
                "scale": 0.35,
                "border": 8,
                "query": query,
                "source_title": result.get("title", ""),
                "source_url": img_url,
            }
            with open(s_yaml_p, "w", encoding="utf-8") as yf:
                yaml.safe_dump(scfg, yf, allow_unicode=True, sort_keys=False)

            applied_count += 1
            print(f"[ok]   【{s_id}】已成功掛載考據圖：{query} -> {result.get('title')}")
            if progress_callback:
                progress_callback(idx, total_matched, f"✅ 已為【{s_id}】套用考據圖：{query}", s_dir=s_dir)

            import time
            time.sleep(1.0)  # 考據圖下載間隔微延遲
        except Exception as exc:
            print(f"[warn] 【{s_id}】考據圖處理失敗: {exc}")
            continue

    return applied_count
