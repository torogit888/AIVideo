from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
import yaml

from aivideo.commands.check import _load_dotenv
from aivideo.gemini_image import get_gemini_client_kwargs
from aivideo.naming import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_VOICE_ID,
    scene_folder_id,
    scene_title_from_narration,
)
from aivideo.spoken import (
    OMNIVOICE_TAG_RE as _OMNIVOICE_TAG_RE,
    _deidentify_extracted_narrator_name,
    deidentify_and_bind_tone,
    extract_outline_leak_phrases,
    extract_tone_spoken_sample,
    is_non_spoken_script_line,
    resolve_host_persona_name,
    sanitize_script_punctuation,
    split_long_narration_line,
)
from aivideo.scene_cut import is_cta_line, merge_trailing_cta_chunks

REPO_ROOT = Path(__file__).resolve().parents[1]

TEXT_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.7-flash",
)


def resolve_text_model_name(model_name: str | None) -> str:
    """將使用者或前端傳入的模型名稱正規化，預設為 gemini-3.8-flash。"""
    m = (model_name or "").strip()
    return m if m else "gemini-3.8-flash"


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

from aivideo.style_prompt import (
    DEFAULT_STYLE_PRESETS,
    STYLES_FILE,
    delete_style_preset,
    is_generic_fallback_prompt,
    load_style_presets,
    resolve_style,
    save_all_style_presets,
    save_style_preset,
    style_lock_instructions,
)

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


def load_tone_info(tone_id: str) -> dict[str, Any]:
    """完整解析口吻範本檔案，提取人設名稱、特質描述、發音引導與核心口白示範。"""
    raw = load_tone_sample(tone_id)
    if not raw:
        return {
            "id": tone_id,
            "name": tone_id,
            "description": "極具感染力、短句頓挫、反詰質疑後驚喜反轉的敘事風格",
            "recommended_voice_instruct": "沉穩、老練、娓娓道來",
            "spoken_sample": "",
            "full_text": "",
        }

    meta: dict[str, Any] = {}
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass

    spoken_sample = extract_tone_spoken_sample(raw)

    return {
        "id": str(meta.get("id") or tone_id),
        "name": str(meta.get("name") or meta.get("title") or tone_id),
        "description": str(meta.get("description") or "極具感染力、短句頓挫、反詰質疑後驚喜反轉的敘事風格"),
        "recommended_voice_instruct": str(meta.get("recommended_voice_instruct") or "沉穩、老練、娓娓道來"),
        "tags": meta.get("tags") or [],
        "spoken_sample": spoken_sample,
        "full_text": raw,
    }


def _strip_outline_preamble(text: str) -> str:
    """移除 AI 在大綱『第一幕』之前多輸出的寒暄前言（例如『好的，我將根據您的核心指示規劃一份大綱...』）。"""
    raw = (text or "").strip()
    if not raw:
        return ""
    match = re.search(
        r"(?m)^[\s#*>-]*(?:【?\s*第一幕|Act\s*1\b|1[\.\、\s]*第一幕)",
        raw,
    )
    if match and match.start() > 0:
        return raw[match.start() :].strip()
    return raw


def build_outline_target_spec(word_count: int = 3500) -> str:
    """依目標字數滑桿動態換算預估片長與建議幕數，避免大綱永遠固定為 4000 字／12~15 分鐘。"""
    wc = max(300, min(5000, int(word_count or 3500)))
    est_min = max(1, round(wc / 220))
    if wc <= 1200:
        acts_range = "4～6 幕"
    else:
        acts_range = "6～8 幕"
    return f"片長約 {est_min} 分鐘（目標約 {wc} 字）的「{acts_range}核心情節大綱與關鍵看點」"


def generate_story_outline(
    topic: str,
    tone_id: str = "michelin_curious",
    model: str | None = None,
    user_prompt: str | None = None,
    word_count: int = 3500,
) -> str:
    """由 AI 聯網檢索並規劃故事的核心情節大綱與關鍵看點，依目標字數滑桿與使用者自訂 Prompt 深化。"""
    _load_dotenv()
    from google import genai
    from google.genai import types

    host_name = resolve_host_persona_name(user_prompt)
    raw_tone_sample = load_tone_sample(tone_id)
    tone_sample = deidentify_and_bind_tone(raw_tone_sample, host_name)
    target_spec = build_outline_target_spec(word_count)

    user_prompt_section = ""
    if user_prompt and user_prompt.strip():
        user_prompt_section = f"""
【使用者核心指示與自訂 Prompt 要求（最高優先級，必須融入各幕規劃）】
{user_prompt.strip()}
請務必緊扣並融入使用者上述指定的開頭台詞、自稱人設（如「大家好，我是{host_name or '頻道主'}！」）、靈感看點或情節要求！
注意：若使用者指定了「開頭: 大家好~我是{host_name or '白兔'}!」，代表這是【第一幕故事口白的開場台詞】，請將其規劃進「第一幕」的開場設計內，切勿將它當作你回覆使用者的 AI 前言寒暄！
"""

    persona_rule = (
        f"- 第一幕開場自稱固定為「{host_name}」（例如以「大家好，我是{host_name}！」開場後直接切入風格範本的破題提問或反差 Hook）。"
        if host_name
        else "- 本篇不加固定頻道主自稱，第一幕請直接以風格範本的反差提問或懸念 Hook 破題。"
    )

    prompt = f"""你是一位頂級專題紀錄片與故事腳本總策劃。
請針對以下主題進行深度資料檢索，規劃一套結構嚴密、高潮迭起、{target_spec}：

【主題】
{topic}
{user_prompt_section}
【指定口吻風格與敘事公式參照（必須 100% 深度模仿其敘事結構、語氣態度與節奏公式）】
{tone_sample if tone_sample else "請使用極具感染力、短句頓挫、反詰質疑後驚喜反轉的敘事風格。"}
請 100% 深度模仿上述口吻範本中的「核心敘事結構與節奏公式」與獨特說話腔調（如破題反詰、犀利吐槽、通俗比喻、核心機制拆解、反噬警示與收尾方式，絕不可寫成平淡通用的罐頭大綱）！
【人設去識別化與開場規範】：
{persona_rule}
- 嚴禁自稱「說書人」、「小編」，亦【絕對禁止】出現任何其他真實 YouTuber 名稱（如「叉雞」等）！只模仿其口吻靈魂，自稱一律使用上方指定設定。

【大綱規劃原則（核心黃金架構）】
1. 請條列 6～8 個獨立幕次，每幕包含：
   - 幕次標題與核心矛盾衝突
   - 關鍵真實歷史/技術細節、數據對抗或人物名場面
   - 此幕要帶給觀眾的懸念或情緒高潮
2. 【第一幕強制要求·時代坐標與歷史舞台鋪陳】：
   第一幕在拋出認知反差 Hook 之後，必須清楚交代故事發生的「時空背景與歷史舞台」（包括具體年代年份、當時的世界地緣格局、社會大環境與時代封閉性），為全篇故事打下紮實的沉浸式世界觀，切忌毫無前情背景直接跳入細節。
3. 【最後一幕要求·歷史餘韻與口吻收尾】：
   最後一幕交代事件的長遠歷史沉澱、深刻反思與餘韻，並依循所選口吻範本的收尾方式自然作結（除非使用者於自訂 Prompt 另有指定，否則切勿硬塞罐頭訂閱推銷詞）。
4. 避免空泛概述，請給出具體人物姓名、時間點、關鍵事件與技術關鍵詞。
5. 排版請簡潔有力，條列式輸出（例如「### 第一幕：...」、「### 第二幕：...」）。
6. 「幕次標題」與「此幕要帶給觀眾的懸念或情緒高潮」是給下一階段編劇看的場記，不是口白。請用內部筆記語氣書寫，後續腳本必須改寫成聽眾聽得懂的台詞，不得把這些欄位原句唸出來。

【輸出格式死命令（嚴禁 AI 客套話前言）】：
- 第一行必須直接從「### 第一幕：...」開始輸出！
- 絕對禁止在第一幕之前輸出任何寒暄、引言、自我介紹或 AI 助理回覆（例如嚴禁出現「好的，...」、「這個主題充滿了...」、「我將根據您的核心指示規劃一份大綱...」等廢話）！

請直接從「### 第一幕」開始輸出繁體中文大綱內容："""

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
                return _strip_outline_preamble(resp.text.strip())
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
    outline: str | None = None,
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
    outline_text = outline if outline is not None else notes

    _load_dotenv()
    from google import genai
    from google.genai import types

    host_name = resolve_host_persona_name(user_prompt)
    tone_info = load_tone_info(tone_id)
    tone_desc = tone_info["description"]
    tone_voice = tone_info["recommended_voice_instruct"]
    tone_sample = deidentify_and_bind_tone(tone_info["spoken_sample"], host_name)
    tone_full_formula = deidentify_and_bind_tone(tone_info["full_text"], host_name)

    user_prompt_section = ""
    if user_prompt and user_prompt.strip():
        user_prompt_section = f"""
【使用者核心指示與指定 Prompt（最高優先級客製化要求，必須 100% 執行）】
{user_prompt.strip()}
請務必將使用者上述指定的開頭台詞、自稱人設（如「大家好，我是{host_name or '白兔'}！」）、劇情看點或視角要求深度落實於腳本中！若使用者有指定開頭，全文第一句必須優先採用使用者指定的開頭！
"""

    notes_section = ""
    if outline_text and outline_text.strip():
        notes_section = f"""
【故事核心大綱與關鍵看點（僅供內部情節骨架，禁止照抄欄位文字）】
{outline_text.strip()}
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

    prompt = f"""你是一位頂級專題紀錄片與故事腳本總編劇。
【核心口吻風格與說話靈魂（最高指導原則：必須 100% 深度模仿此口吻，絕不可寫成平淡通用旁白）】：
- 頻道主身份自稱：{host_name if host_name else "無自稱（直接切入故事）"}
- 風格定位與語氣靈魂：{tone_desc}
- 解說姿態與情感基調：{tone_voice}
請完全沉浸並 100% 模仿下方【指定口吻風格示範文本】的說話姿態、招牌句型、語氣轉折、反詰吐槽與收尾節奏，為我撰寫全篇腳本：

【主題】
介紹：{topic}
{user_prompt_section}
{notes_section}
【指定口吻風格示範文本與敘事公式（請 100% 深度模仿其句型、破題姿態、口頭禪與頓挫節奏）】
{tone_full_formula if tone_full_formula else tone_sample or "請使用極具感染力、短句頓挫、反詰質疑後驚喜反轉的敘事風格。"}

【基本需求與字數規模配額（極重要）】
- 字數規模：目標嚴格控制在約 {word_count} 字左右（容許區間：{min_words} ～ {max_words} 字，絕不可草率縮水亦不可無節制灌水）
- 總口白行數要求：全文必須輸出約 {target_total_lines} 行獨立口白（一句一行）
- 篇幅與幕次分配（關鍵）：
  * 故事請涵蓋 6～8 個完整轉折幕次（起承轉合、危機爆發、生死對決、技術/商業本質拆解、高潮反轉與歷史昇華）。
  * 每一幕必須包含充足飽滿的口白量（平均每幕請分配約 {target_lines_per_scene} 行台詞），情節層層推進，嚴格禁止浮光掠影般草草收尾。
- 前情鋪陳與時空背景引導（極重要，告別突兀）：
  * 第一幕在以認知反差提問或懸念破題之後，必須緊接著用 3～5 句交代故事的「時空座標與歷史舞台」（交代具體年代年份、當時的世界地緣大格局、時代背景與面臨的巨大死局），帶領聽眾身臨其境進入那個時代，切忌在沒有任何前情背景交代下直接跳入事件細節！
- 說書人口語自然與通順度（極重要）：
  * 語言必須極度自然、通俗口語、生動流暢，有如一位老練的說書人在聽眾耳邊娓娓道來。
  * 句子之間聲氣貫通、語氣自然銜接（善用「但問題是，」、「更不可思議的是，」、「回到當時的大環境來看，」、「你可能很難想像，」等自然口語過渡詞），避免生硬乾癟的公文報告腔或零碎條列感。
- 片尾自然收尾規範（嚴禁罐頭推銷）：
  * 全篇結尾請嚴格依循上方【指定口吻風格示範文本與敘事公式】的結尾方式自然收束（例如歷史餘韻、開放式提問、精闢洞察或簡短道別）。
  * 除非使用者在【使用者核心指示與指定 Prompt】中明確要求加入訂閱詞，否則【嚴禁】在結尾硬塞「請記得訂閱我們的頻道並打開小鈴鐺」、「給予支持」、「對我們持續產出內容至關重要」等生硬的罐頭行銷口白！
- 人設與開場規範（極為關鍵）：
  * 若上方【使用者核心指示與指定 Prompt】中有指定開頭台詞或自稱（例如「開頭: 大家好~我是白兔!」），全篇第一句口白必須 100% 嚴格採用該指定開頭（並符合標點規範，如「大家好，我是白兔！」）！
  * 【絕對嚴格禁止】自稱「說書人」、「小編」，亦【絕對嚴格禁止】照抄口吻風格範本中的原作者名或特定稱謂（如「叉雞」等）！口吻範本僅供學習句型節奏與敘事結構。
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

請直接以指定口吻的強烈個人敘事節奏輸出逐行口白內容（若有指定開頭自稱請於第一句輸出，不要輸出與腳本無關的 AI 前言，切勿自稱小編或照抄其他真實 YTR 名稱如叉雞，嚴禁輸出幕次或結構標題）："""

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
                return sanitize_script_punctuation(resp.text.strip(), outline_notes=outline_text)
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

    host_name = resolve_host_persona_name(current_script[:200])
    tone_info = load_tone_info(tone_id)
    tone_desc = tone_info["description"]
    tone_voice = tone_info["recommended_voice_instruct"]
    tone_sample = deidentify_and_bind_tone(tone_info["spoken_sample"], host_name)

    target_lines = max(20, round(target_word_count / 20))
    min_expand_words = int(target_word_count * 0.9)
    max_expand_words = int(target_word_count * 1.1)

    prompt = f"""你是一位頂級專題故事與紀錄片資深編劇。
【核心口吻風格與人設特質（最高指導原則：必須 100% 深度模仿此口吻）】：
- 風格定位與語氣靈魂：{tone_desc}
- 解說姿態與情感基調：{tone_voice}
請完全沉浸並 100% 模仿下方口吻示範文本的說話姿態與標誌性敘事腔調，進行「深度情節擴寫與細節補強」，將現有口白精準擴寫為目標約 {target_word_count} 字的深度故事：

【主題】
{topic if topic else "原腳本核心主題"}

【原始腳本口白】
{current_script.strip()}

【指定口吻風格示範文本（100% 模仿其句型、轉折與語氣）】
{tone_sample if tone_sample else "請使用極具感染力、短句頓挫、反詰質疑後驚喜反轉的敘事風格。"}

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
   - 【絕對嚴禁自稱「說書人」、「小編」或照抄風格範本中的「叉雞」等名稱】！若原始腳本開頭已有自稱（如「大家好，我是白兔！」），請完整保留該開頭自稱。
   - 外國人名、機構名一律中文通譯，避免英文。
   - 自然嵌入 OmniVoice 情緒標籤（如 [surprise-wa]、[sigh]、[question-ei] 等，每 4~6 句至多 1 個）。

請直接以指定口吻的強烈個人敘事節奏輸出擴寫後的完整逐行口白腳本（保留原腳本開頭自稱，不要輸出與腳本無關的 AI 前言，切勿自稱小編或叉雞，嚴禁輸出結構標籤）："""

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
4. "environment_anchor" is the shared world art style, atmospheric lighting, line quality, and color palette — NEVER include specific characters, specific props, or single-scene events in environment_anchor.

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
      "entity_type": "character" or "object" (strictly "character" for human persons/miners/leaders/figures, "object" for inanimate items/ships/vehicles/props),
      "appearance": "English visual description. For humans: face, hair, clothing. For objects/vehicles: authentic physical model, materials, colors (NO face/limbs)."
    }}
  ],
  "environment_anchor": "English description of overall world aesthetic, architectural era, lighting mood, and color palette (no specific characters or props)..."
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


def _extract_json_list_from_response(raw_text: str) -> list[Any] | None:
    """從 LLM 回應中寬容提取 JSON 陣列（支援 markdown code fence 與外層 dict 包裝）。"""
    text = (raw_text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        parsed = json.loads(text)
    except Exception:
        m = re.search(r"\[[\s\S]*\]", text)
        if not m:
            return None
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            return None

    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for k in ("scenes", "plans", "items", "data", "results"):
            if isinstance(parsed.get(k), list):
                return parsed[k]
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return None


def _normalize_single_visual_plan(
    item: Any,
    valid_char_ids: set[str],
) -> dict[str, object] | None:
    if isinstance(item, dict):
        p_text = str(item.get("image_prompt") or item.get("prompt") or "").strip()
        raw_ids = item.get("character_ids")
        c_ids = (
            [str(cid).strip() for cid in raw_ids if str(cid).strip() in valid_char_ids]
            if isinstance(raw_ids, list)
            else []
        )
    elif isinstance(item, str):
        p_text = item.strip()
        c_ids = []
    else:
        return None

    # 移除不小心混入的中文風格名稱或教學詞彙
    p_text = re.sub(
        r"\b(?:educational storyboard|educational panels)\b",
        "2D cartoon illustration",
        p_text,
        flags=re.IGNORECASE,
    )
    p_text = re.sub(r"[\u4e00-\u9fff]+", "", p_text).strip(" ,，")
    if not p_text or is_generic_fallback_prompt(p_text):
        return None
    return {
        "image_prompt": p_text,
        "character_ids": c_ids,
    }


def _generate_visual_plans_chunk(
    batch_narrations: list[str],
    *,
    anchor_rules: str,
    style: dict[str, str],
    style_lock: str,
    valid_char_ids: set[str],
    is_final_chunk: bool = False,
) -> list[dict[str, object] | None]:
    """針對單一小批次（最多 10 幕）呼叫 Gemini 產生英文 image_prompt 與 character_ids。"""
    from aivideo.commands.check import _load_dotenv
    _load_dotenv()
    from google import genai
    from google.genai import types

    tag_pattern = re.compile(r"\[[a-zA-Z0-9_\-]+\]")
    items_text = "\n".join([f"[{i+1}] {tag_pattern.sub('', n).strip()}" for i, n in enumerate(batch_narrations)])
    style_en_medium = style.get("prefix") or "2D cartoon illustration, clean line art, cel shading"

    cta_rule = (
        "7. If the final scene contains ending channel subscription or call-to-action lines (e.g. 'like and subscribe', 'see you next time', '點個喜歡', '訂閱頻道'), strictly IGNORE the subscription wording and focus the visual prompt completely on the grand narrative conclusion, final historical scene, or character climax.\n"
        if is_final_chunk
        else ""
    )

    prompt = f"""You are a master storyboard visual director and concept artist.
Analyze the following {len(batch_narrations)} sequential scene narrations from a video documentary.
For each scene, first determine which recurring entities (`character_ids`) from the Character & Entity Bible actually appear in that scene, and then write a detailed, vivid visual text-to-image prompt strictly in 100% ENGLISH (`image_prompt`).

{style_lock}
{anchor_rules}

CRITICAL PROMPT CRAFTING REQUIREMENTS:
1. Every `image_prompt` MUST be written completely in 100% ENGLISH (ABSOLUTELY NO Chinese characters).
2. Formulate the visual prompt strictly in the locked project art medium ({style_en_medium}). Do NOT contradict it with photorealistic 3D or live-action styles.
3. Translate each scene narration into a CONCRETE, VISUALLY SPECIFIC SCENE matching EXACTLY what that narration describes: specific characters/people, era-accurate setting/location, dynamic action or posture, tangible props, lighting mood, and camera framing (wide establishing shot, medium shot, close-up, low angle) in 16:9 widescreen composition.
4. ONLY include visual descriptions of catalog entities whose `id` you placed in that scene's `character_ids`. If `character_ids` is `[]`, depict the historical environment, architecture, anonymous figures, or objects mentioned in that scene's narration WITHOUT inserting any catalog protagonist or prop.
5. Keep inanimate objects strictly physical (never give objects cartoon human eyes, limbs, or faces).
6. NEVER include any dialogue, speech bubbles, quotes, text, subtitles, words, letters, logos, or watermarks.
{cta_rule}8. Output EXACTLY a JSON array of {len(batch_narrations)} objects in the exact same order as the input scenes (1 to {len(batch_narrations)}):
[
  {{
    "index": 1,
    "character_ids": ["entity_id_1"],
    "image_prompt": "wide establishing shot of [specific subject, setting, and action from scene 1 in {style_en_medium[:60]}], 16:9 widescreen composition"
  }}
]

Scenes:
{items_text}
"""
    results: list[dict[str, object] | None] = [None] * len(batch_narrations)
    for model_name in get_candidate_text_models():
        try:
            client = genai.Client(**get_gemini_client_kwargs(model=model_name))
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.35,
                    response_mime_type="application/json",
                ),
            )
            if not resp.text:
                continue
            parsed_list = _extract_json_list_from_response(resp.text)
            if not parsed_list:
                continue

            # 若回傳陣列長度與批次相同，直接依序對應；若長度略有差異則優先看 item["index"] 再依序填入
            if len(parsed_list) == len(batch_narrations):
                for idx, item in enumerate(parsed_list):
                    results[idx] = _normalize_single_visual_plan(item, valid_char_ids)
            else:
                for pos, item in enumerate(parsed_list):
                    target_idx = None
                    if isinstance(item, dict) and str(item.get("index") or "").isdigit():
                        cand_idx = int(item["index"]) - 1
                        if 0 <= cand_idx < len(batch_narrations):
                            target_idx = cand_idx
                    if target_idx is None and pos < len(batch_narrations) and results[pos] is None:
                        target_idx = pos
                    if target_idx is not None:
                        results[target_idx] = _normalize_single_visual_plan(item, valid_char_ids)

            if any(r is not None for r in results):
                break
        except Exception as exc:
            print(f"[warn] 分鏡 Prompt 批次生成呼叫 {model_name} 失敗: {exc}")
            continue

    return results


def batch_generate_scene_visual_plans(
    narrations: list[str],
    subject_anchor: str = "",
    environment_anchor: str = "",
    characters: list[dict[str, str]] | None = None,
    style_key: str = "",
) -> list[dict[str, object]]:
    """呼叫 Gemini 依據專案全域視覺風格與視覺錨點，為每一幕先判定實際登場的定裝 ID (character_ids)，
    再將中文旁白轉換為只包含登場主體的專業英文畫面提示詞 (image_prompt)。
    採每批最多 10 幕分段請求，並對個別漏幕自動單獨補跑，防止長腳本一次請求失敗退回空白罐頭句。
    回傳格式: [{"image_prompt": str, "character_ids": list[str]}, ...]
    """
    if not narrations:
        return []

    from aivideo.visual_anchors import character_bible_for_prompts

    char_list = characters or []
    valid_char_ids = {str(ch.get("id") or "").strip() for ch in char_list if ch.get("id")}
    bible = character_bible_for_prompts(char_list)

    clean_bible = bible.replace("educational storyboard", "2D animation").replace("educational panels", "clean 2D panels") if bible else ""
    clean_sub_anchor = subject_anchor.replace("educational storyboard", "2D animation").replace("educational panels", "clean 2D panels")
    clean_env_anchor = environment_anchor.replace("educational storyboard", "2D animation").replace("educational panels", "clean 2D panels")

    anchor_rules = ""
    if clean_bible or clean_sub_anchor or clean_env_anchor:
        if clean_bible:
            subject_rule = (
                "AVAILABLE CHARACTER & ENTITY BIBLE (Reference Catalog):\n"
                f"{clean_bible}\n"
                "- STRICT SCENE CASTING RULE: For each scene, first decide `character_ids` — the exact list of `id`s from the catalog above that ACTUALLY appear in that specific scene's narration (including clear pronoun references like 'he', 'this scientist', 'the glue' resolved from adjacent scenes).\n"
                "- WHEN TO USE EMPTY `character_ids: []`: If a scene narration describes general history, corporate background, macroeconomic context, anonymous crowds/colleagues/executives, pure landscapes, or conceptual transitions where NO catalog entity is physically present, `character_ids` MUST be `[]`.\n"
                "- STRICT ZERO-HALLUCINATION RULE: If an entity's `id` is NOT in that scene's `character_ids`, you are STRICTLY FORBIDDEN from mentioning its name or visual traits in that scene's `image_prompt`! Never force unused protagonists or props into the frame (NO superimposed faces/eyes, NO tiny protagonist standing in the background, NO floating phantom props).\n"
                "- STRICT NO-ANTHROPOMORPHISM: Never give inanimate objects/ships/bottles human eyes, faces, arms, or legs."
            )
        else:
            subject_rule = (
                f'- MAIN SUBJECT ANCHOR: ONLY when the main protagonist/object is actually present in the scene narration, incorporate these details: "{clean_sub_anchor}". If the scene is a general setting or transition without the main subject, do NOT include it.'
            )
        env_rule = ""
        if clean_env_anchor:
            env_rule = (
                f'\n- LIGHTING & PALETTE ANCHOR: Use the general lighting mood, line quality, and color palette from "{clean_env_anchor}", '
                "but ALWAYS set the actual location/room/building strictly according to each scene's narration (never force a specific lab, basement, or object from the environment description into unrelated scenes)."
            )
        anchor_rules = f"""
VISUAL CONTINUITY & SCENE CASTING RULES:
{subject_rule}{env_rule}
"""

    style = resolve_style(style_key)
    style_lock = style_lock_instructions(style_key)

    BATCH_SIZE = 10
    all_plans: list[dict[str, object] | None] = []
    total = len(narrations)

    for start_idx in range(0, total, BATCH_SIZE):
        batch = narrations[start_idx : start_idx + BATCH_SIZE]
        is_last = (start_idx + BATCH_SIZE) >= total
        chunk_plans = _generate_visual_plans_chunk(
            batch,
            anchor_rules=anchor_rules,
            style=style,
            style_lock=style_lock,
            valid_char_ids=valid_char_ids,
            is_final_chunk=is_last,
        )
        all_plans.extend(chunk_plans)

    # 若有少數單幕因對齊問題仍為 None，針對該單幕獨立重試一次
    for idx, plan in enumerate(all_plans):
        if plan is None and narrations[idx].strip():
            retry_res = _generate_visual_plans_chunk(
                [narrations[idx]],
                anchor_rules=anchor_rules,
                style=style,
                style_lock=style_lock,
                valid_char_ids=valid_char_ids,
                is_final_chunk=(idx == total - 1),
            )
            if retry_res and retry_res[0] is not None:
                all_plans[idx] = retry_res[0]

    # 保底：使用純英文風格 prefix 與環境基調，絕不混入中文風格名或寫實戲劇光字眼
    fallback_prefix = style.get("prefix") or "2D cartoon illustration, clean line art, cel shading"
    env_fallback = f", {clean_env_anchor[:160]}" if clean_env_anchor else ""
    final_plans: list[dict[str, object]] = []
    for plan in all_plans:
        if isinstance(plan, dict) and plan.get("image_prompt"):
            final_plans.append(plan)
        else:
            final_plans.append(
                {
                    "image_prompt": f"Wide establishing shot{env_fallback}, {fallback_prefix[:140]}, 16:9 widescreen composition",
                    "character_ids": [],
                }
            )
    return final_plans


def translate_single_scene_prompt(
    narration: str,
    style_key: str = "",
    subject_anchor: str = "",
    environment_anchor: str = "",
    characters: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """為單一分鏡依據專案全域視覺風格與錨點，將中文旁白轉譯為英文出圖 Prompt 與實際出場 character_ids。"""
    plans = batch_generate_scene_visual_plans(
        [narration],
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
        characters=characters,
        style_key=style_key,
    )
    return plans[0] if plans else {"image_prompt": "", "character_ids": []}


def _normalize_pip_plan_item(item: Any) -> dict[str, str] | None:
    """將 AI 回傳的單幕考據決策正規化為 {"query": str, "media_type": "video"|"image", "mode": "broll"|"spotlight"|"pip"}。"""
    if not item:
        return None
    if isinstance(item, str):
        q = item.strip()
        if not q or q.lower() == "null":
            return None
        return {"query": q, "media_type": "image", "mode": "pip"}
    if isinstance(item, dict):
        raw_q = item.get("query")
        if not raw_q or str(raw_q).strip().lower() in ("", "null", "none"):
            return None
        q = str(raw_q).strip()
        m_type = str(item.get("media_type") or "").strip().lower()
        mode = str(item.get("mode") or "").strip().lower()
        if mode == "broll" or m_type == "video":
            return {"query": q, "media_type": "video", "mode": "broll"}
        if mode in ("spotlight", "focus", "black_bg", "fullscreen"):
            return {"query": q, "media_type": "image", "mode": "spotlight"}
        return {"query": q, "media_type": "image", "mode": "pip"}
    return None


def batch_detect_pip_plans(
    narrations: list[str],
    topic: str = "",
    subject_anchor: str = "",
) -> list[dict[str, str] | None]:
    """
    呼叫 Gemini AI 批次分析各場景分鏡台詞，全權由 AI 決定：
    1. 哪幾幕需要真實考據素材（不需要則為 None）
    2. 每一幕適合抓「動態考據影片 (video / broll)」、「黑底全螢幕原照 (image / spotlight)」還是「角落畫中畫小卡 (image / pip)」
    3. 精簡準確的英文搜尋關鍵字 (query)
    """
    if not narrations:
        return []

    from aivideo.commands.check import _load_dotenv
    _load_dotenv()
    from google import genai
    from google.genai import types

    scene_items = [{"index": idx + 1, "text": text} for idx, text in enumerate(narrations)]

    context_lines = []
    if topic:
        context_lines.append(f"- Documentary Core Topic: {topic}")
    if subject_anchor:
        context_lines.append(f"- Core Subject Anchor & Era: {subject_anchor}")
    context_block = f"\nDOCUMENTARY CONTEXT:\n" + "\n".join(context_lines) + "\n" if context_lines else ""

    prompt = f"""You are a master archival visual researcher and senior documentary film director.
Analyze the following {len(narrations)} scene narrations for a documentary video.{context_block}
For EACH scene, decide:
1. Whether displaying authentic archival visual evidence (a real historical/documentary video clip or real photograph) will boost audience immersion and documentary credibility.
2. If YES, decide the best `media_type` ("video" or "image") and presentation `mode` ("broll", "spotlight", or "pip"):
   - `media_type: "video", mode: "broll"` (Fullscreen Archival Video / YouTube Footage):
     Choose this when the scene describes a DYNAMIC real-world action, historical newsreel event, crowd/street activity, sports/record-breaking feat, factory/production line, flight/sailing/launch, scientific experiment in motion, or era footage where real moving footage exists on YouTube / archives (approx. 15%~30% of archival scenes).
   - `media_type: "image", mode: "spotlight"` (Fullscreen Black-Background Archival Photo):
     Choose this when the scene describes a pivotal historical turning point, famous historical photograph, signed treaty/contract/book cover close-up, historical map, or dramatic reveal where the real photo should take center stage on a pure black background.
   - `media_type: "image", mode: "pip"` (Corner Picture-in-Picture Photo Card over AI Illustration):
     Choose this when the scene mentions a specific historical person/portrait, company/institution, building/location, or specific object/vehicle while the main background remains the story's AI illustration.
3. If the scene is generic opening/closing greeting, pure emotional transition, or dialogue without a concrete real-world entity, output `null`.

CRITICAL QUERY GUIDELINES:
- Aim for 45%~70% of scenes overall to have archival evidence (`pip`, `spotlight`, or `broll`).
- KEEP `query` CONCISE (2 to 4 core English nouns MAX, e.g. "British food rationing", "Sir Hugh Beaver", "Guinness Book of Records 1955", "Roger Bannister mile 1954"). Do NOT pad queries with 7-word descriptions.

Scenes:
{json.dumps(scene_items, ensure_ascii=False, indent=2)}

OUTPUT FORMAT:
Return a JSON array with EXACTLY {len(narrations)} items corresponding to the scenes in order. Each item must be either `null` or an object `{{"query": "...", "media_type": "video"|"image", "mode": "broll"|"spotlight"|"pip"}}`:
[
  null,
  {{"query": "British food rationing", "media_type": "video", "mode": "broll"}},
  {{"query": "Sir Hugh Beaver", "media_type": "image", "mode": "pip"}},
  {{"query": "Guinness Book of Records 1955", "media_type": "image", "mode": "spotlight"}}
]
"""

    for model_name in get_candidate_text_models():
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
                parsed = _extract_json_list_from_response(resp.text)
                if isinstance(parsed, list):
                    result = [_normalize_pip_plan_item(item) for item in parsed]
                    while len(result) < len(narrations):
                        result.append(None)
                    return result[: len(narrations)]
        except Exception:
            continue

    return [None] * len(narrations)


def batch_detect_pip_queries(
    narrations: list[str],
    topic: str = "",
    subject_anchor: str = "",
) -> list[str | None]:
    """向下相容介面：回傳每幕的考據檢索詞字串或 None。"""
    plans = batch_detect_pip_plans(narrations, topic=topic, subject_anchor=subject_anchor)
    return [p["query"] if isinstance(p, dict) and p.get("query") else None for p in plans]


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
    style_key: str = "otomo_katsuhiro",
    subject_anchor: str = "",
    environment_anchor: str = "",
    topic: str = "",
    characters: list[dict[str, str]] | None = None,
    outline: str | None = None,
) -> list[dict[str, object]]:
    """將逐行台詞依據 AI 語意情節與設定的視覺節奏 (Visual Pacing: fast / balanced / slow) 自動切分為分鏡場景，
    並為每場分鏡產生英文提示詞與前置分析考據實體 (PiP)。"""
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

    # AI 智能語意切分 (結合視覺節奏：快 / 標準 / 慢)
    chunks = ai_semantic_chunk_script(
        clean_lines,
        visual_pacing=visual_pacing,
        topic=topic,
    )

    # 自動吸收合併片尾訂閱呼籲語 (CTA)，確保訂閱口白留在故事最後一幕，不產生孤立新分鏡
    chunks = merge_trailing_cta_chunks(chunks)

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
    visual_plans = batch_generate_scene_visual_plans(
        narrations,
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
        characters=characters,
        style_key=style_key,
    )
    pip_plans = batch_detect_pip_plans(
        narrations,
        topic=topic,
        subject_anchor=subject_anchor,
    )

    scenes: list[dict[str, object]] = []
    for idx, (chunk, narration) in enumerate(zip(chunks, narrations), start=1):
        plan = visual_plans[idx - 1] if idx - 1 < len(visual_plans) else {}
        img_prompt = (
            str(plan.get("image_prompt") or "")
            if isinstance(plan, dict) and plan.get("image_prompt")
            else "Cinematic wide angle shot, dramatic lighting, 16:9 widescreen composition"
        )
        char_ids = (
            list(plan.get("character_ids"))
            if isinstance(plan, dict) and isinstance(plan.get("character_ids"), list)
            else []
        )
        pip_plan = pip_plans[idx - 1] if idx - 1 < len(pip_plans) else None
        q = pip_plan.get("query") if isinstance(pip_plan, dict) else None
        pip_mtype = pip_plan.get("media_type") if isinstance(pip_plan, dict) else None
        pip_mode = pip_plan.get("mode") if isinstance(pip_plan, dict) else None

        scenes.append({
            "id": scene_folder_id(idx),
            "index": idx,
            "title": scene_title_from_narration(narration),
            "narration": narration,
            "sentences": list(chunk),
            "image_prompt": img_prompt,
            "character_ids": char_ids,
            "pip_query": q,
            "pip_media_type": pip_mtype,
            "pip_mode": pip_mode,
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
請深度分析以下提供的參考口白文本或 YouTube 逐字稿，100% 原汁原味提煉出該講者的「說書人口吻風格規範與範本」，同時將講者真實姓名／頻道名去識別化：

【參考文本】
{text[:5000]}

【任務與輸出規範（極重要：口吻 100% 深度模仿，僅將名字去識別化）】
請深度剖析該文本最具辨識度的破題節奏、說話腔調、吐槽反詰、轉折口頭禪、邏輯鋪陳與收尾習慣（絕不可改寫成平淡無奇的通用旁白），並以 JSON 格式輸出以下欄位：
1. "id": 英文唯一識別碼（小寫英數字與底線，長度約 8~25 字元，請以風格特徵命名，勿包含特定 YouTuber 真名，例如 "urban_dark_expose", "tech_business_deepdive", "suspense_noir"）。
2. "title": 具備高度辨識度的通用說書風格中文名稱（請以風格特色命名，勿直接填入原 YouTuber 真名，例如："社會暗面犀利揭秘風", "硬核商業反差解構風", "懸疑奇案冷冽剖析風"）。
3. "tags": 3~6 個精確標籤陣列（例如：["社會觀察", "深度揭秘", "犀利吐槽", "通俗比喻", "故事性"]）。
4. "recommended_voice_instruct": 適合 OmniVoice 語音模型的發音人語氣引導詞（格式範例："女，青年，中音调"、"男，青年，沉穩低音"、"男，中年，沉穩且富有洞察力"）。
5. "description": 一句話簡要描述與特徵（約 40~80 字，說明適用題材、開場鉤子 Hook、標誌性語氣、比喻與節奏特色，勿出現原 YouTuber 真名）。
6. "sample_narration": 從參考文本中精選或重構出一段約 250~450 字的「精華示範口白」，並嚴格符合專案規範：
   * 【口吻 100% 原汁原味保留、僅將人名/頻道名去識別化】：必須 100% 保留該講者最具辨識度的說話腔調、破題節奏、吐槽句式（如「我只能說...」、「信不信由你，確實有」）、轉折口頭禪與收尾習慣，絕不可改成平淡的通用旁白；但若參考文本中出現原講者或原頻道的真實名稱（例如「大家好，我是叉雞」、「我是老高」等），請一律將該名字替換為通用佔位符「{{頻道主}}」（例如：「大家好，我是{{頻道主}}，」），切勿把原作者真名寫死在範本中！
   * 標點符號只允許使用全形逗號「，」、問號「？」、感嘆號「！」（絕對嚴禁句號「。」、冒號「：」、頓號「、」、各類引號「」“”‘’、破折號——與括號）。
   * 問號「？」與感嘆號「！」必須極度克制（90%以上使用全形逗號「，」銜接或換行斷句，問號感嘆號每 10~15 句至多出現 1 次）。
   * 自然且克制地嵌入 OmniVoice 官方副語言情緒標籤（如 [surprise-wa]、[surprise-oh]、[question-ei]、[sigh]、[laughter]、[confirmation-en]、[dissatisfaction-hnn] 等，平均每 4~6 句至多 1 個）。
   * 外語名詞、人名、機構名一律標準中譯。
7. "structure_formula": 核心敘事結構與節奏公式（以 Markdown 條列 4~7 個步驟成片法，必須精確提煉該講者專屬的開場、轉折、吐槽與收尾典型句型！若典型句型中有自稱，請一律寫作「{{頻道主}}」，勿出現原作者真名）。
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
    desc = _deidentify_extracted_narrator_name(
        str(data.get("description") or "由 Vertex AI Gemini Flash 智慧萃取之說書人口吻範本。")
    )
    raw_sample = _deidentify_extracted_narrator_name(str(data.get("sample_narration") or "").strip())
    sample = sanitize_script_punctuation(raw_sample)
    formula = _deidentify_extracted_narrator_name(str(data.get("structure_formula") or "").strip())
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
    script_text: str | None = None,
    visual_pacing: str = "balanced",
) -> Path:
    job_dir = REPO_ROOT / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir = job_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

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
        "visual_pacing": visual_pacing or "balanced",
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
            "model": (image_model or DEFAULT_IMAGE_MODEL).strip(),
            "resolution": "1K",
            "aspect_ratio": "16:9",
            "style": style_key,
        },
        "subtitle": {
            "mode": "none",
            "font": subtitle_font_for_job(),
            "font_size": 48,
        },
        "kenburns": "slow_zoom_in",
    }
    save_job_config(job_dir, job_yaml)

    # 寫入 script.md（直接寫入純口白文字，不寫入「畫面：／旁白：」導演筆記再二次覆寫）
    if script_text is not None:
        final_script_md = script_text
    else:
        final_script_md = "\n".join(
            str(s.get("narration") or "").strip()
            for s in scenes
            if str(s.get("narration") or "").strip()
        )
    (job_dir / "script.md").write_text(final_script_md, encoding="utf-8")

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
            "character_ids": list(s.get("character_ids") or []) if "character_ids" in s else [],
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
            ai_mode = str(s.get("pip_mode") or "").strip().lower()
            ai_mtype = str(s.get("pip_media_type") or "").strip().lower()
            if ai_mode in ("pip", "spotlight", "broll"):
                auto_mode = ai_mode
            else:
                auto_mode = infer_pip_mode(q, str(s.get("narration", "")))
            chosen_mtype = "video" if (ai_mtype == "video" or auto_mode == "broll") else "image"
            scfg["pip"] = {
                "enabled": True,  # 預設啟用考據，出圖或一鍵全流程時自動下載生效
                "media_type": chosen_mtype,
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

    visual_plans = batch_generate_scene_visual_plans(
        narrations,
        subject_anchor=subject_anchor,
        environment_anchor=environment_anchor,
        characters=characters,
        style_key=style_key,
    )

    updated_count = 0
    for idx, (s_yaml_p, scfg) in enumerate(scene_yamls):
        if idx < len(visual_plans):
            plan = visual_plans[idx]
            scfg["image_prompt"] = str(plan.get("image_prompt") or "")
            if isinstance(plan.get("character_ids"), list):
                scfg["character_ids"] = list(plan["character_ids"])
            scfg.pop("visual_concept", None)
            with open(s_yaml_p, "w", encoding="utf-8") as f:
                yaml.safe_dump(scfg, f, allow_unicode=True, sort_keys=False)
            updated_count += 1

    return updated_count

