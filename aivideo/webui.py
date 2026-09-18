from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 確保專案根目錄在 sys.path 中，避免 streamlit 直接執行腳本時找不到 aivideo 套件
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st
import yaml

from aivideo.commands.check import _load_dotenv, has_gemini_credentials
from aivideo.commands.compose import run_compose
from aivideo.commands.images import run_images
from aivideo.commands.preview import generate_preview_html
from aivideo.commands.srt import generate_srt
from aivideo.commands.tts import run_tts
from aivideo.gemini_image import generate_image

# 自動熱重載子模組，防止 Streamlit 常駐時快取舊版 sys.modules 導致 ImportError
import importlib
import aivideo.story_generator
importlib.reload(aivideo.story_generator)

from aivideo.story_generator import (
    STYLE_PRESETS,
    create_job_bundle,
    delete_style_preset,
    extract_story_visual_anchors,
    generate_story_script,
    load_style_presets,
    parse_script_lines_to_scenes,
    regenerate_job_scene_prompts,
    save_style_preset,
)

_load_dotenv()

st.set_page_config(
    page_title="AIVideo · AI 說書人工作室",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished dark-mode dashboard
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #38bdf8;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .stCard {
        background-color: #1e293b;
        border-radius: 10px;
        padding: 1.2rem;
        border: 1px solid #334155;
        margin-bottom: 1rem;
    }
    .badge-ok {
        background-color: #065f46;
        color: #34d399;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_available_jobs() -> list[str]:
    jobs_dir = REPO_ROOT / "jobs"
    if not jobs_dir.is_dir():
        return []
    return sorted(
        [p.name for p in jobs_dir.iterdir() if p.is_dir() and not p.name.startswith("_")],
        reverse=True,
    )


def get_available_tones() -> dict[str, str]:
    tones_dir = REPO_ROOT / "assets" / "tones"
    if not tones_dir.is_dir():
        return {}
    res = {}
    for p in sorted(tones_dir.glob("*.md")):
        if p.name == "README.md":
            continue
        res[p.stem] = p.stem
    return res


def get_available_voices() -> list[str]:
    voices_dir = REPO_ROOT / "assets" / "voices"
    if not voices_dir.is_dir():
        return ["female01"]
    return sorted([p.name for p in voices_dir.iterdir() if p.is_dir()])


def sanitize_id(raw_id: str) -> str:
    cleaned = re.sub(r"[^\w\-]", "_", raw_id.strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_")


def save_tone_file(tone_id: str, content: str) -> Path:
    tones_dir = REPO_ROOT / "assets" / "tones"
    tones_dir.mkdir(parents=True, exist_ok=True)
    target = tones_dir / f"{tone_id}.md"
    target.write_text(content.strip() + "\n", encoding="utf-8")
    return target


def delete_tone_file(tone_id: str) -> bool:
    target = REPO_ROOT / "assets" / "tones" / f"{tone_id}.md"
    if target.is_file():
        target.unlink()
        return True
    return False


def save_voice_profile(
    voice_id: str,
    display_name: str,
    mode: str = "clone",
    speed: float = 1.0,
    position_temp: float = 0.1,
    steps: int = 32,
    instruct: str = "",
    ref_text: str = "",
    wav_bytes: bytes | None = None,
) -> Path:
    voice_dir = REPO_ROOT / "assets" / "voices" / voice_id
    voice_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = voice_dir / "voice.yaml"
    cfg = {}
    if yaml_path.is_file():
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            cfg = {}
    cfg.update({
        "id": voice_id,
        "display_name": display_name,
        "engine": "omnivoice",
        "model": "OmniVoice-bf16",
        "mode": mode,
        "dtype": "fp16",
        "attention": "eager",
        "steps": int(steps),
        "speed": float(speed),
        "seed": cfg.get("seed", 42),
        "position_temperature": float(position_temp),
        "class_temperature": float(cfg.get("class_temperature", 0.0)),
        "instruct": instruct.strip(),
    })
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    if ref_text.strip():
        (voice_dir / "reference.txt").write_text(ref_text.strip() + "\n", encoding="utf-8")
    if wav_bytes is not None:
        (voice_dir / "reference.wav").write_bytes(wav_bytes)
    return voice_dir


def delete_voice_profile(voice_id: str) -> bool:
    voice_dir = REPO_ROOT / "assets" / "voices" / voice_id
    if voice_dir.is_dir():
        shutil.rmtree(voice_dir)
        return True
    return False


# --- Sidebar ---
st.sidebar.title("🎬 AIVideo 控制台")

# 狀態檢查
comfy_url = os.environ.get("COMFY_URL", "http://comfyui:8188").rstrip("/")
gemini_ok = has_gemini_credentials()

st.sidebar.markdown("### 系統狀態")
col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    st.markdown(f"**Gemini:** {'🟢 就緒' if gemini_ok else '🔴 缺少金鑰'}")
with col_s2:
    st.markdown(f"**ComfyUI:** 🟢 8188")

st.sidebar.markdown("---")
jobs_list = get_available_jobs()

if not jobs_list:
    st.sidebar.selectbox("📁 選擇當前專案 (Job)", options=["無專案"], index=0, disabled=True)
    selected_job_name = None
else:
    # 若有外部指令（新建專案或刪除專案），在 widget 實例化前安全更新 widget 狀態
    if "target_job" in st.session_state:
        target = st.session_state.pop("target_job")
        if target in jobs_list:
            st.session_state["sidebar_job_select"] = target
        elif jobs_list:
            st.session_state["sidebar_job_select"] = jobs_list[0]
    elif "sidebar_job_select" not in st.session_state or st.session_state["sidebar_job_select"] not in jobs_list:
        st.session_state["sidebar_job_select"] = jobs_list[0]

    job_idx = jobs_list.index(st.session_state["sidebar_job_select"])

    col_sb1, col_sb2 = st.sidebar.columns([4, 1])
    with col_sb1:
        selected_job_name = st.selectbox(
            "📁 選擇當前專案 (Job)",
            options=jobs_list,
            index=job_idx,
            key="sidebar_job_select",
        )
    with col_sb2:
        st.write("")
        st.write("")
        if st.button("🔄", help="重新整理專案目錄清單", key="btn_refresh_jobs"):
            st.rerun()

tab_create, tab_produce, tab_film, tab_assets = st.tabs([
    "✍️ 故事發想與腳本",
    "🎞️ 分鏡看板與生成",
    "📺 1080p 成片預覽",
    "🎙️ 音色與風格庫",
])


# =========================================================================
# TAB 1: 故事發想與腳本生成
# =========================================================================
with tab_create:
    st.markdown('<div class="main-header">故事發想與腳本創作工作室</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">透過 Gemini 聯網搜集資料，套用指定說書人口吻，生成嚴格遵守「每行一句話、標點只允許 ，？！、盡量無英文」的 YouTube 深度說書腳本。</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        topic_input = st.text_input(
            "📌 故事主題",
            value="美國太空總署羅曼太空望遠鏡的秘密",
            placeholder="例如：光刻機霸主艾司摩爾的崛起傳奇、旅行者號金唱片的孤獨旅程",
        )
        word_count_slider = st.slider(
            "📏 需求字數規模",
            min_value=300,
            max_value=5000,
            value=1500,
            step=100,
            help="以 100 字為單位精細調整。1500 字約 5~6 分鐘精華，4000 字約 12~15 分鐘完整專題。",
        )
        search_toggle = st.checkbox("🌐 開啟 Google 即時聯網檢索事實 (Search Grounding)", value=True)

    with col2:
        tones_dict = get_available_tones()
        selected_tone = st.selectbox(
            "🎭 選擇說書人口吻風格 (Tone)",
            options=list(tones_dict.keys()) if tones_dict else ["tech_business_deepdive"],
            index=0,
            format_func=lambda x: f"{x} ({'杜比硬核科普' if 'deepdive' in x else ('米其林商業反轉' if 'michelin' in x else x)})",
        )
        styles_dict = load_style_presets()
        selected_style = st.selectbox(
            "🎨 選擇畫面視覺風格 (Style)",
            options=list(styles_dict.keys()),
            index=0,
            format_func=lambda x: styles_dict.get(x, {}).get("name", x),
        )

        s_info = styles_dict.get(selected_style, {})
        preview_rel = s_info.get("preview", "")
        preview_path = REPO_ROOT / preview_rel if preview_rel and not preview_rel.startswith("http") else None
        with st.expander("🖼️ 查看當前風格示範預覽", expanded=True):
            if preview_path and preview_path.is_file():
                st.image(str(preview_path), caption=f"示範：{s_info.get('name', selected_style)}", use_container_width=True)
            elif preview_rel.startswith("http"):
                st.image(preview_rel, caption=f"示範：{s_info.get('name', selected_style)}", use_container_width=True)
            if s_info.get("description"):
                st.caption(f"**風格特色：** {s_info['description']}")

        selected_voice = st.selectbox(
            "🎙️ 選擇發音人 (Voice)",
            options=get_available_voices(),
            index=0,
        )

    if st.button("🚀 呼叫 Gemini 聯網搜集資料並生成腳本口白", type="primary"):
        with st.spinner("正在聯網搜集真實資料並以指定說書人口吻撰寫逐行腳本，請稍候..."):
            try:
                script_result = generate_story_script(
                    topic=topic_input,
                    tone_id=selected_tone,
                    word_count=word_count_slider,
                    search_grounding=search_toggle,
                )
                st.session_state["generated_script"] = script_result
                st.success("腳本生成大功告成！你可以在下方文字框進行手動微調與修訂：")
            except Exception as exc:
                st.error(f"腳本生成失敗：{exc}")

    col_st_hdr, col_st_load = st.columns([2.5, 1])
    with col_st_hdr:
        st.markdown("#### 📝 口白腳本編輯區（每行一句台詞，支援線上修訂）")
    with col_st_load:
        if selected_job_name and selected_job_name != "無專案":
            if st.button(f"📥 載入【{selected_job_name}】腳本", help="將左側選中專案的原始腳本載入至此編輯區"):
                s_file = REPO_ROOT / "jobs" / selected_job_name / "script.md"
                if s_file.is_file():
                    s_lines = []
                    for line in s_file.read_text(encoding="utf-8").splitlines():
                        if line.startswith("旁白："):
                            s_lines.append(line[3:].strip())
                    if s_lines:
                        st.session_state["generated_script"] = "\n".join(s_lines)
                    else:
                        st.session_state["generated_script"] = s_file.read_text(encoding="utf-8")
                    st.success(f"已成功載入專案【{selected_job_name}】之腳本台詞！")
                    st.rerun()

    script_text = st.text_area(
        "口白腳本文字內容",
        label_visibility="collapsed",
        value=st.session_state.get("generated_script", ""),
        height=320,
    )

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        sents_per_scene = st.slider("🖼️ 每張圖片搭配句數", min_value=1, max_value=3, value=3, help="建議 2~3 句換一張圖，觀看節奏最佳！")

    with col_btn2:
        job_slug_input = st.text_input(
            "📁 新 Job 資料夾名稱（ASCII slug）",
            value=f"{datetime.now().strftime('%Y%m%d')}_new_story",
        )

    if st.button("✨ 將上方腳本正式建立為新專案 (Create Job)", type="primary"):
        if not script_text.strip():
            st.warning("請先生成或在文字框輸入腳本台詞！")
        else:
            with st.spinner("正在提煉全片主體特徵與環境光影錨點 (Visual Anchors)..."):
                anchors = extract_story_visual_anchors(topic=topic_input, script_text=script_text)
                sub_anchor = anchors.get("subject_anchor", "")
                env_anchor = anchors.get("environment_anchor", "")

            with st.spinner("正在切分分鏡並融合視覺錨點產生專業英文提示詞..."):
                scenes = parse_script_lines_to_scenes(
                    script_text,
                    sentences_per_scene=sents_per_scene,
                    style_key=selected_style,
                    subject_anchor=sub_anchor,
                    environment_anchor=env_anchor,
                )
                job_dir = create_job_bundle(
                    job_id=job_slug_input,
                    title=topic_input,
                    scenes=scenes,
                    style_key=selected_style,
                    voice_id=selected_voice,
                    subject_anchor=sub_anchor,
                    environment_anchor=env_anchor,
                )
                # 設定目標切換專案，安全重載
                st.session_state["target_job"] = job_slug_input
                st.toast(f"✅ 專案【{job_slug_input}】建立成功！已自動切換。", icon="🎉")
                st.rerun()


# =========================================================================
# TAB 2: 分鏡看板與生成
# =========================================================================
with tab_produce:
    if not selected_job_name or selected_job_name == "無專案":
        st.info("請先在左側選單選擇或建立一個 Job 專案。")
    else:
        job_path = REPO_ROOT / "jobs" / selected_job_name
        job_yaml_path = job_path / "job.yaml"
        if not job_yaml_path.is_file():
            st.error(f"找不到 {selected_job_name} 的 job.yaml！")
        else:
            with open(job_yaml_path, "r", encoding="utf-8") as f:
                current_job_cfg = yaml.safe_load(f) or {}

            st.markdown(f'<div class="main-header">{current_job_cfg.get("title", selected_job_name)}</div>', unsafe_allow_html=True)
            st.markdown(f"**專案路徑：** `jobs/{selected_job_name}` ｜ **發音人：** `{current_job_cfg.get('voice_id')}` ｜ **圖片風格：** `{current_job_cfg.get('image', {}).get('style', '自訂')}`")

            # 腳本資料檢視面板
            script_file = job_path / "script.md"
            with st.expander("📜 查看當前專案完整腳本與分鏡台詞 (script.md)", expanded=False):
                if script_file.is_file():
                    script_content = script_file.read_text(encoding="utf-8")
                    total_chars = len(re.findall(r'[\u4e00-\u9fff]', script_content))
                    st.markdown(f"**腳本檔案：** `jobs/{selected_job_name}/script.md` ｜ **中文字數：** 約 `{total_chars}` 字")

                    scol_l, scol_r = st.columns([1.6, 1])
                    with scol_l:
                        st.markdown("##### 📝 逐行口白劇本")
                        st.text_area("完整腳本內容", value=script_content, height=260, disabled=True, key=f"script_txt_{selected_job_name}")
                    with scol_r:
                        st.markdown("##### 📌 專案設定快照")
                        st.markdown(f"- **專案主題：** {current_job_cfg.get('title', selected_job_name)}")
                        st.markdown(f"- **綁定發音人：** `{current_job_cfg.get('voice_id')}`")
                        st.markdown(f"- **畫面視覺風格：** `{current_job_cfg.get('image', {}).get('style')}`")
                        st.markdown(f"- **16:9 解析度：** `{current_job_cfg.get('frame', {}).get('deliver_width', 1920)}x{current_job_cfg.get('frame', {}).get('deliver_height', 1080)}`")
                        st.markdown(f"- **推鏡運鏡：** `{current_job_cfg.get('kenburns', 'slow_zoom_in')}`")
                        st.markdown(f"- **提示詞前綴：** `{current_job_cfg.get('style_prefix', '')[:50]}...`")
                else:
                    st.info("該專案未找到 script.md 檔案。")

            with st.expander("⚙️ 調整當前專案設定（切換發音人或視覺風格）", expanded=False):
                ecol1, ecol2, ecol3 = st.columns([1, 1, 0.8])
                with ecol1:
                    cur_v = current_job_cfg.get("voice_id", "female01")
                    all_v = get_available_voices()
                    v_idx = all_v.index(cur_v) if cur_v in all_v else 0
                    new_v = st.selectbox("🎙️ 切換發音人", options=all_v, index=v_idx, key="cfg_switch_voice")
                with ecol2:
                    cur_s = current_job_cfg.get("image", {}).get("style", "otomo_katsuhiro")
                    all_s = load_style_presets()
                    all_s_keys = list(all_s.keys())
                    s_idx = all_s_keys.index(cur_s) if cur_s in all_s_keys else 0
                    new_s = st.selectbox(
                        "🎨 切換視覺風格",
                        options=all_s_keys,
                        index=s_idx,
                        format_func=lambda x: all_s.get(x, {}).get("name", x),
                        key="cfg_switch_style",
                    )
                    new_s_info = all_s.get(new_s, {})
                    new_prev_rel = new_s_info.get("preview", "")
                    new_prev_p = REPO_ROOT / new_prev_rel if new_prev_rel and not new_prev_rel.startswith("http") else None
                    if new_prev_p and new_prev_p.is_file():
                        st.image(str(new_prev_p), caption=f"示範：{new_s_info.get('name', new_s)}", use_container_width=True)
                    elif new_prev_rel.startswith("http"):
                        st.image(new_prev_rel, caption=f"示範：{new_s_info.get('name', new_s)}", use_container_width=True)
                with ecol3:
                    st.write("")
                    st.write("")
                    if st.button("💾 儲存並套用至專案", key="btn_apply_job_cfg"):
                        current_job_cfg["voice_id"] = new_v
                        if "image" not in current_job_cfg or not isinstance(current_job_cfg["image"], dict):
                            current_job_cfg["image"] = {}
                        current_job_cfg["image"]["style"] = new_s
                        if new_s in all_s:
                            current_job_cfg["style_prefix"] = all_s[new_s]["prefix"]
                            current_job_cfg["style_negative"] = all_s[new_s]["negative"]
                        with open(job_yaml_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump(current_job_cfg, f, allow_unicode=True, sort_keys=False)
                        st.success("專案設定已更新！後續批次生圖或配音將直接生效。")
                        st.rerun()

            # 視覺一致性錨點與主體定裝圖
            anchors_cfg = current_job_cfg.get("visual_anchors", {})
            hero_anchor_png = job_path / "hero_anchor.png"

            with st.expander("🎭 專案視覺一致性錨點與主體定裝 (Visual Continuity Anchors)", expanded=False):
                st.markdown(
                    "支援**「圖片參考（Image-to-Image）」**與**「文字特徵錨點」**雙重鎖定。出圖時模型將直接讀取定裝圖，並將文字錨點注入各分鏡，達到最高畫面連貫性！"
                )
                va_col1, va_col2 = st.columns([1.1, 1.7])
                with va_col1:
                    st.markdown("##### 🖼️ 主體定裝基準圖 (Hero Shot)")
                    if hero_anchor_png.is_file():
                        st.image(str(hero_anchor_png), caption="全片主體視覺基準（已就緒）", use_container_width=True)
                        if st.button("🗑️ 移除此定裝圖", key=f"btn_rm_hero_{selected_job_name}"):
                            hero_anchor_png.unlink(missing_ok=True)
                            st.rerun()
                    else:
                        st.info("尚未設定主體定裝圖（可點擊下方生成或自行上傳）")

                    # 方式 A：由 AI 生成定裝圖
                    if st.button("🎲 產生主體定裝圖 (Hero Shot)", key=f"btn_gen_hero_{selected_job_name}"):
                        cur_sub = anchors_cfg.get("subject", current_job_cfg.get("title", selected_job_name))
                        cur_env = anchors_cfg.get("environment", "Cinematic lighting, 16:9 widescreen composition")
                        style_pfx = current_job_cfg.get("style_prefix", "")
                        hero_prompt = f"{style_pfx}，Hero concept portrait shot, {cur_sub}, {cur_env}, 16:9 widescreen, masterpiece".strip("，")
                        with st.spinner("正在呼叫 Gemini 生成主體定裝基準圖..."):
                            try:
                                generate_image(hero_prompt, hero_anchor_png)
                                st.success("已成功生成主體定裝基準圖！")
                                st.rerun()
                            except Exception as e:
                                st.error(f"定裝圖生成失敗: {e}")

                    # 方式 B：自行上傳參考圖
                    up_hero = st.file_uploader(
                        "📤 或上傳自訂主體參考圖 (JPG/PNG)",
                        type=["png", "jpg", "jpeg"],
                        key=f"up_hero_{selected_job_name}",
                    )
                    if up_hero is not None:
                        hero_anchor_png.write_bytes(up_hero.read())
                        st.success("已成功儲存自訂主體參考圖！")
                        st.rerun()

                    # 圖片參考開關
                    use_ref_chk = st.checkbox(
                        "🖼️ 出圖時將此圖作為視覺參考 (Image Reference Conditioning)",
                        value=bool(anchors_cfg.get("use_image_reference", True)),
                        key=f"chk_use_ref_{selected_job_name}",
                        help="啟用後，Gemini 將以多模態方式直接讀取此參考圖，鎖定五官、機械與服裝特徵！",
                    )
                    if use_ref_chk != anchors_cfg.get("use_image_reference", True):
                        anchors_cfg["use_image_reference"] = use_ref_chk
                        current_job_cfg["visual_anchors"] = anchors_cfg
                        with open(job_yaml_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump(current_job_cfg, f, allow_unicode=True, sort_keys=False)
                        st.rerun()

                with va_col2:
                    st.markdown("##### 📌 核心視覺特徵錨點 (英文)")
                    cur_sub_text = st.text_area(
                        "主體外觀特徵錨點 (Subject Anchor - 主角/機器/生物結構)",
                        value=anchors_cfg.get("subject", ""),
                        height=90,
                        key=f"sub_anchor_{selected_job_name}",
                    )
                    cur_env_text = st.text_area(
                        "環境與光影基調錨點 (Environment Anchor - 背景空間結構、色溫、光影類型)",
                        value=anchors_cfg.get("environment", ""),
                        height=90,
                        key=f"env_anchor_{selected_job_name}",
                    )

                    col_anc_btn1, col_anc_btn2 = st.columns([1, 1.5])
                    with col_anc_btn1:
                        if st.button("💾 儲存錨點設定", key=f"btn_save_anchor_{selected_job_name}"):
                            current_job_cfg["visual_anchors"] = {
                                "subject": cur_sub_text.strip(),
                                "environment": cur_env_text.strip(),
                                "use_image_reference": use_ref_chk,
                            }
                            with open(job_yaml_path, "w", encoding="utf-8") as f:
                                yaml.safe_dump(current_job_cfg, f, allow_unicode=True, sort_keys=False)
                            st.success("已更新專案視覺錨點！")
                            st.rerun()

                    with col_anc_btn2:
                        if st.button("🔄 依最新錨點重新產生所有分鏡 Prompt", key=f"btn_sync_prompts_{selected_job_name}"):
                            with st.spinner("正在依據最新視覺錨點批次重構全片所有分鏡之英文提示詞..."):
                                count = regenerate_job_scene_prompts(
                                    job_dir=job_path,
                                    subject_anchor=cur_sub_text.strip(),
                                    environment_anchor=cur_env_text.strip(),
                                )
                                current_job_cfg["visual_anchors"] = {
                                    "subject": cur_sub_text.strip(),
                                    "environment": cur_env_text.strip(),
                                    "use_image_reference": use_ref_chk,
                                }
                                with open(job_yaml_path, "w", encoding="utf-8") as f:
                                    yaml.safe_dump(current_job_cfg, f, allow_unicode=True, sort_keys=False)
                                st.success(f"大功告成！已依最新視覺錨點同步更新 {count} 場分鏡之英文提示詞！")
                                st.rerun()

            with st.expander("🗑️ 刪除當前專案 (Job)", expanded=False):
                st.warning(f"即將徹底刪除專案資料夾 `jobs/{selected_job_name}`（包含所有分鏡、圖片與語音）。")
                confirm_del_job = st.checkbox("確認刪除此專案 (此操作無法復原)", key=f"chk_del_job_{selected_job_name}")
                if st.button("🗑️ 確定刪除專案", key=f"btn_del_job_{selected_job_name}"):
                    if confirm_del_job:
                        shutil.rmtree(job_path)
                        st.session_state["target_job"] = ""
                        st.success(f"已刪除專案【{selected_job_name}】！")
                        st.rerun()
                    else:
                        st.warning("請先勾選確認方塊。")

            # 頂部快捷操作按鈕組
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)

            class CmdArgs:
                def __init__(self, job, force=False, scene=None, count=1, draft=False, new_seed=False, keep_seed=False, progress_callback=None):
                    self.job = str(job)
                    self.force = force
                    self.scene = scene
                    self.count = count
                    self.draft = draft
                    self.new_seed = new_seed
                    self.keep_seed = keep_seed
                    self.progress_callback = progress_callback

            with col_b1:
                if st.button("🎨 批次出圖 (Images)"):
                    p_bar = st.progress(0, text="正在呼叫 Gemini API 產生 16:9 畫面...")
                    def on_img_prog(cur, tot, msg):
                        frac = min(1.0, max(0.0, cur / max(1, tot)))
                        p_bar.progress(frac, text=f"🎨 出圖進度 ({cur}/{tot}) - {msg}")
                    res = run_images(CmdArgs(job_path, force=True, progress_callback=on_img_prog), progress_callback=on_img_prog)
                    p_bar.progress(1.0, text="✅ 批次出圖完成！")
                    st.rerun()

            with col_b2:
                if st.button("🎙️ 批次配音 (Voice Clone)"):
                    p_bar = st.progress(0, text="正在透過 ComfyUI 進行逐句聲音克隆合成...")
                    def on_tts_prog(cur, tot, msg):
                        frac = min(1.0, max(0.0, cur / max(1, tot)))
                        p_bar.progress(frac, text=f"🎙️ 配音進度 ({cur}/{tot}) - {msg}")
                    res = run_tts(CmdArgs(job_path, force=True, progress_callback=on_tts_prog), progress_callback=on_tts_prog)
                    p_bar.progress(1.0, text="✅ 批次配音完成！")
                    st.rerun()

            with col_b3:
                if st.button("🎬 合成 1080p 成片 (Compose)"):
                    with st.spinner("正在透過 FFmpeg 合成 Ken Burns 推鏡與 1080p ASS 字幕..."):
                        run_compose(CmdArgs(job_path))
                        generate_preview_html(job_path)
                        st.success("成片合成完成！請切換到「📺 1080p 成片預覽」分頁播放！")

            with col_b4:
                if st.button("🚀 全流程一鍵重新生成 (All-in-One)", type="primary"):
                    p_bar = st.progress(0, text="🚀 [1/3 出圖] 正在準備呼叫 Gemini API...")
                    def on_all_img(cur, tot, msg):
                        frac = 0.45 * (cur / max(1, tot))
                        p_bar.progress(frac, text=f"🎨 [1/3 出圖] ({cur}/{tot}) - {msg}")

                    def on_all_tts(cur, tot, msg):
                        frac = 0.45 + 0.45 * (cur / max(1, tot))
                        p_bar.progress(frac, text=f"🎙️ [2/3 配音] ({cur}/{tot}) - {msg}")

                    run_images(CmdArgs(job_path, force=True, progress_callback=on_all_img), progress_callback=on_all_img)
                    p_bar.progress(0.45, text="🎙️ [2/3 配音] 正在透過 ComfyUI 進行逐句聲音克隆...")
                    run_tts(CmdArgs(job_path, force=True, progress_callback=on_all_tts), progress_callback=on_all_tts)
                    p_bar.progress(0.92, text="🎬 [3/3 成片] 正在透過 FFmpeg 合成 1080p 影片與燒錄字幕...")
                    run_compose(CmdArgs(job_path))
                    generate_preview_html(job_path)
                    p_bar.progress(1.0, text="🎉 全流程重新生成大功告成！")
                    st.success("全流程重新生成大功告成！")
                    st.rerun()

            st.markdown("---")
            st.markdown("### 🎞️ 分鏡看板 (Storyboard)")

            scenes_dir = job_path / "scenes"
            scene_dirs = sorted([p for p in scenes_dir.iterdir() if p.is_dir()]) if scenes_dir.is_dir() else []
            total_scenes = len(scene_dirs)

            # 統計所有場景即時完成度
            img_ready_cnt = 0
            wav_ready_cnt = 0
            total_dur_sec = 0.0
            scene_status_list = []

            for s_dir in scene_dirs:
                has_i = (s_dir / "image.png").is_file()
                has_w = (s_dir / "speech.wav").is_file()
                s_dur = 0.0
                speech_j = s_dir / "speech.json"
                if speech_j.is_file():
                    try:
                        s_dur = float(json.loads(speech_j.read_text(encoding="utf-8")).get("duration_sec", 0.0))
                    except Exception:
                        pass
                if has_i:
                    img_ready_cnt += 1
                if has_w:
                    wav_ready_cnt += 1
                    total_dur_sec += s_dur
                scene_status_list.append({
                    "dir": s_dir,
                    "has_img": has_i,
                    "has_wav": has_w,
                    "duration": s_dur,
                })

            film_file = job_path / "compose" / "film.mp4"

            # 頂部即時完成指標卡片
            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            with mcol1:
                p_img = (img_ready_cnt / total_scenes * 100) if total_scenes else 0
                st.metric("🖼️ 畫面完成度", f"{img_ready_cnt} / {total_scenes}", f"{p_img:.0f}%")
            with mcol2:
                p_wav = (wav_ready_cnt / total_scenes * 100) if total_scenes else 0
                st.metric("🎙️ 語音完成度", f"{wav_ready_cnt} / {total_scenes}", f"{p_wav:.0f}%")
            with mcol3:
                m_dur = int(total_dur_sec // 60)
                s_dur = int(total_dur_sec % 60)
                st.metric("⏱️ 總旁白時長", f"{m_dur}分 {s_dur:02d}秒")
            with mcol4:
                st.metric("🎬 1080p 成片", "🟢 已合成" if film_file.is_file() else "⏳ 待合成")

            # 看板過濾器
            filter_view = st.radio(
                "🔍 看板過濾顯示：",
                options=["全部場景", "僅看待處理 (缺圖或缺音)", "僅看已就緒 (圖音皆齊)"],
                horizontal=True,
                key=f"filter_{selected_job_name}",
            )

            rendered_cnt = 0
            for item in scene_status_list:
                s_dir = item["dir"]
                has_i = item["has_img"]
                has_w = item["has_wav"]
                s_dur = item["duration"]

                if filter_view == "僅看待處理 (缺圖或缺音)" and has_i and has_w:
                    continue
                if filter_view == "僅看已就緒 (圖音皆齊)" and not (has_i and has_w):
                    continue

                rendered_cnt += 1
                s_id = s_dir.name
                s_yaml_p = s_dir / "scene.yaml"
                if not s_yaml_p.is_file():
                    continue
                with open(s_yaml_p, "r", encoding="utf-8") as f:
                    scfg = yaml.safe_load(f) or {}

                img_p = s_dir / "image.png"
                wav_p = s_dir / "speech.wav"

                dur_str = f"{s_dur:.1f}s" if s_dur > 0 else "—"

                # 徽章標籤
                status_badge = "✅ 就緒" if (has_i and has_w) else ("⚠️ 缺音" if has_i else ("⚠️ 缺圖" if has_w else "🔴 待產出"))
                img_tag = "🟢 圖" if has_i else "⚪ 缺圖"
                wav_tag = "🟢 音" if has_w else "⚪ 缺音"

                expander_label = f"【{s_id}】{scfg.get('title', s_id)} ｜ {status_badge} ({img_tag} ｜ {wav_tag}) ｜ ⏱️ {dur_str}"

                with st.expander(expander_label, expanded=(not has_i or not has_w)):
                    scol1, scol2 = st.columns([1, 1.5])
                    with scol1:
                        if img_p.is_file():
                            st.image(str(img_p), use_container_width=True)
                        else:
                            st.info("尚未產出畫面")

                        if wav_p.is_file():
                            st.audio(str(wav_p))
                        else:
                            st.info("尚未合成語音")

                        # 單場重抽卡按鈕組
                        btn_c1, btn_c2 = st.columns(2)
                        with btn_c1:
                            if st.button(f"🎲 重抽這張圖", key=f"btn_img_{s_id}"):
                                with st.spinner(f"重新呼叫 Gemini 抽圖【{s_id}】..."):
                                    run_images(CmdArgs(job_path, scene=s_id, force=True, new_seed=True))
                                    st.rerun()
                        with btn_c2:
                            if st.button(f"🎙️ 重錄這段聲音", key=f"btn_tts_{s_id}"):
                                with st.spinner(f"重新呼叫 ComfyUI 克隆語音【{s_id}】..."):
                                    run_tts(CmdArgs(job_path, scene=s_id, force=True))
                                    st.rerun()

                    with scol2:
                        st.markdown("**旁白台詞 (Narration)：**")
                        st.write(scfg.get("narration", ""))
                        st.markdown("**畫面提示詞 (English Image Prompt)：**")
                        cur_prompt_val = scfg.get("image_prompt", "")
                        edited_prompt = st.text_area(
                            f"提示詞編輯【{s_id}】",
                            label_visibility="collapsed",
                            value=cur_prompt_val,
                            height=85,
                            key=f"prompt_edit_{selected_job_name}_{s_id}",
                        )
                        if edited_prompt != cur_prompt_val:
                            if st.button(f"💾 儲存修改提示詞", key=f"btn_save_p_{s_id}"):
                                scfg["image_prompt"] = edited_prompt
                                with open(s_yaml_p, "w", encoding="utf-8") as f:
                                    yaml.safe_dump(scfg, f, allow_unicode=True, sort_keys=False)
                                st.success(f"已更新【{s_id}】英文畫面提示詞！")
                                st.rerun()

            if rendered_cnt == 0:
                st.info(f"在「{filter_view}」篩選條件下無符合的場景。")


# =========================================================================
# TAB 3: 成片預覽與下載
# =========================================================================
with tab_film:
    st.markdown('<div class="main-header">1080p 寬銀幕成片預覽</div>', unsafe_allow_html=True)
    if not selected_job_name or selected_job_name == "無專案":
        st.info("請先選擇專案。")
    else:
        film_file = REPO_ROOT / "jobs" / selected_job_name / "compose" / "film.mp4"
        srt_file = REPO_ROOT / "jobs" / selected_job_name / "compose" / "timeline.srt"
        ass_file = REPO_ROOT / "jobs" / selected_job_name / "compose" / "timeline.ass"
        preview_file = REPO_ROOT / "jobs" / selected_job_name / "preview.html"

        if film_file.is_file():
            st.video(str(film_file))

            dcol1, dcol2, dcol3, dcol4 = st.columns(4)
            with dcol1:
                with open(film_file, "rb") as f:
                    st.download_button("📥 下載 1080p 影片 (MP4)", data=f.read(), file_name=f"{selected_job_name}.mp4", mime="video/mp4")
            with dcol2:
                if srt_file.is_file():
                    with open(srt_file, "rb") as f:
                        st.download_button("📥 下載 SRT 字幕檔", data=f.read(), file_name="timeline.srt", mime="text/plain")
            with dcol3:
                if ass_file.is_file():
                    with open(ass_file, "rb") as f:
                        st.download_button("📥 下載 ASS 1080p 樣式字幕", data=f.read(), file_name="timeline.ass", mime="text/plain")
            with dcol4:
                if preview_file.is_file():
                    st.markdown(f"[在新分頁打開 HTML 故事板]({preview_file.as_uri()})")
        else:
            st.warning("目前該專案尚未合成成片，請在「🎞️ 分鏡看板與生成」分頁點選「🎬 合成 1080p 成片」！")


# =========================================================================
# TAB 4: 音色庫與語氣庫管理
# =========================================================================
with tab_assets:
    st.markdown('<div class="main-header">資源庫管理中心 (Assets Studio)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">直接在控制台新增、編輯、測試與刪除說書人口吻 (Tone)、發音人角色庫 (Voice) 與畫面視覺風格 (Style)。</div>',
        unsafe_allow_html=True,
    )

    subtab_tone, subtab_voice, subtab_style = st.tabs([
        "🎭 說書人口吻風格 (Tone)",
        "🎙️ 發音人音色庫 (Voice)",
        "🎨 畫面視覺風格 (Style)",
    ])

    # ---------------------------------------------------------------------
    # SUBTAB 1: 說書人口吻管理 (Tone)
    # ---------------------------------------------------------------------
    with subtab_tone:
        col_t1, col_t2 = st.columns([1.2, 1])

        with col_t1:
            st.markdown("### 📋 現有口吻檢視與編輯")
            tones_dict = get_available_tones()
            if not tones_dict:
                st.info("目前尚無口吻風格檔案。")
            else:
                tone_keys = list(tones_dict.keys())
                cur_tone = st.selectbox(
                    "選擇要編輯的口吻風格",
                    options=tone_keys,
                    key="tone_manage_select",
                )
                tone_file_path = REPO_ROOT / "assets" / "tones" / f"{cur_tone}.md"
                cur_content = tone_file_path.read_text(encoding="utf-8") if tone_file_path.is_file() else ""

                edit_tone_content = st.text_area(
                    f"【{cur_tone}】口吻範本與規則 Markdown",
                    value=cur_content,
                    height=360,
                    key=f"tone_edit_content_{cur_tone}",
                )

                col_ts1, col_ts2 = st.columns([1, 1])
                with col_ts1:
                    if st.button("💾 儲存口吻修改", key=f"btn_save_tone_{cur_tone}"):
                        save_tone_file(cur_tone, edit_tone_content)
                        st.success(f"已成功更新口吻風格【{cur_tone}】！")
                        st.rerun()

                with col_ts2:
                    with st.expander("🗑️ 刪除此口吻風格", expanded=False):
                        st.warning(f"即將刪除 assets/tones/{cur_tone}.md。")
                        confirm_del_tone = st.checkbox(
                            "確認刪除此口吻風格",
                            key=f"chk_del_tone_{cur_tone}",
                        )
                        if st.button("🗑️ 確定刪除", key=f"btn_del_tone_{cur_tone}"):
                            if confirm_del_tone:
                                delete_tone_file(cur_tone)
                                st.success(f"已刪除口吻風格【{cur_tone}】！")
                                st.rerun()
                            else:
                                st.warning("請先勾選確認方塊。")

        with col_t2:
            st.markdown("### ➕ 新增自訂說書人口吻風格")
            st.markdown(
                "新增的口吻範本會存入 `assets/tones/<ID>.md`，Gemini 故事發想生成腳本時會強制參照範本口吻與句式結構。"
            )
            new_tone_raw_id = st.text_input(
                "口吻英文 ID (例如: history_mystery, culinary_detective)",
                placeholder="僅允許英數與下劃線",
                key="new_tone_raw_id",
            )
            new_tone_id = sanitize_id(new_tone_raw_id)
            if new_tone_raw_id and new_tone_id != new_tone_raw_id:
                st.caption(f"自動格式化 ID 為：`{new_tone_id}`")

            default_tone_template = """# 口吻風格：自訂故事說書人

## 核心人設
- 專業但極具懸念的說書視角，善用反轉、數據對比與名場面描寫。

## 行文節奏與規範
- 一行一句口白台詞，適合逐句 TTS 語音合成。
- 盡量不要出現英文單字或縮寫，名詞與人名一律中譯。
- 標點符號只允許使用全形逗號「，」、問號「？」、感嘆號「！」（嚴禁句號、冒號、引號、頓號）。
- 單句長度控制在 15~35 字之間，節奏明快。
"""
            new_tone_content = st.text_area(
                "口吻範本與規則規範 (Markdown)",
                value=default_tone_template,
                height=320,
                key="new_tone_content_input",
            )

            if st.button("✨ 建立新口吻風格", type="primary", key="btn_create_tone"):
                if not new_tone_id:
                    st.warning("請填寫口吻 ID！")
                elif (REPO_ROOT / "assets" / "tones" / f"{new_tone_id}.md").is_file():
                    st.warning(f"口吻 ID 【{new_tone_id}】已存在，請更換名稱或直接在左側編輯。")
                else:
                    save_tone_file(new_tone_id, new_tone_content)
                    st.success(f"成功建立新口吻風格【{new_tone_id}】！已同步至選單。")
                    st.rerun()

    # ---------------------------------------------------------------------
    # SUBTAB 2: 發音人音色庫管理 (Voice)
    # ---------------------------------------------------------------------
    with subtab_voice:
        col_v1, col_v2 = st.columns([1.2, 1])

        with col_v1:
            st.markdown("### 🎙️ 現有發音人角色庫")
            voices_list = get_available_voices()
            if not voices_list:
                st.info("尚無可用發音人。")
            else:
                cur_voice = st.selectbox(
                    "選擇要檢視或編輯的發音人",
                    options=voices_list,
                    key="voice_manage_select",
                )
                v_dir = REPO_ROOT / "assets" / "voices" / cur_voice
                vyaml_p = v_dir / "voice.yaml"
                vwav_p = v_dir / "reference.wav"
                vtxt_p = v_dir / "reference.txt"

                vcfg = {}
                if vyaml_p.is_file():
                    try:
                        with open(vyaml_p, "r", encoding="utf-8") as f:
                            vcfg = yaml.safe_load(f) or {}
                    except Exception:
                        pass

                st.markdown(f"**角色目錄：** `assets/voices/{cur_voice}/`")
                if vwav_p.is_file():
                    st.audio(str(vwav_p))
                else:
                    st.warning("⚠️ 此角色缺少 reference.wav 參考音訊！")

                edit_v_name = st.text_input(
                    "發音人顯示名稱",
                    value=vcfg.get("display_name", cur_voice),
                    key=f"vname_{cur_voice}",
                )
                col_vc1, col_vc2 = st.columns(2)
                with col_vc1:
                    mode_opts = ["clone", "design"]
                    cur_mode_val = vcfg.get("mode", "clone")
                    mode_idx = mode_opts.index(cur_mode_val) if cur_mode_val in mode_opts else 0
                    edit_v_mode = st.selectbox(
                        "合成模式 (Mode)",
                        options=mode_opts,
                        index=mode_idx,
                        key=f"vmode_{cur_voice}",
                    )
                with col_vc2:
                    edit_v_speed = st.slider(
                        "語速 (Speed)",
                        min_value=0.5,
                        max_value=2.0,
                        value=float(vcfg.get("speed", 1.0)),
                        step=0.05,
                        help="OmniVoice 範圍 0.5~2.0。0.8 為放慢穩健，1.0 為標準。",
                        key=f"vspeed_{cur_voice}",
                    )

                col_vc3, col_vc4 = st.columns(2)
                with col_vc3:
                    edit_v_temp = st.slider(
                        "位置溫度 (Position Temp)",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(vcfg.get("position_temperature", 0.1)),
                        step=0.05,
                        key=f"vtemp_{cur_voice}",
                    )
                with col_vc4:
                    edit_v_steps = st.slider(
                        "推論步數 (Steps)",
                        min_value=16,
                        max_value=50,
                        value=int(vcfg.get("steps", 32)),
                        step=2,
                        key=f"vsteps_{cur_voice}",
                    )

                cur_ref_text = vtxt_p.read_text(encoding="utf-8").strip() if vtxt_p.is_file() else ""
                edit_v_reftext = st.text_area(
                    "參考音逐字稿 (reference.txt - 克隆模式必備)",
                    value=cur_ref_text,
                    height=80,
                    key=f"vtxt_{cur_voice}",
                )

                replace_wav = st.file_uploader(
                    "替換參考音訊 (WAV/MP3，5~15秒乾淨語音)",
                    type=["wav", "mp3"],
                    key=f"rep_wav_{cur_voice}",
                )

                col_vs1, col_vs2 = st.columns([1, 1])
                with col_vs1:
                    if st.button("💾 儲存音色設定變更", key=f"btn_save_voice_{cur_voice}"):
                        wav_bytes = replace_wav.read() if replace_wav is not None else None
                        save_voice_profile(
                            voice_id=cur_voice,
                            display_name=edit_v_name,
                            mode=edit_v_mode,
                            speed=edit_v_speed,
                            position_temp=edit_v_temp,
                            steps=edit_v_steps,
                            instruct=str(vcfg.get("instruct", "")),
                            ref_text=edit_v_reftext,
                            wav_bytes=wav_bytes,
                        )
                        st.success(f"已更新發音人角色【{cur_voice}】！")
                        st.rerun()

                with col_vs2:
                    with st.expander("🗑️ 刪除此音色角色", expanded=False):
                        st.warning(f"即將刪除 assets/voices/{cur_voice}/（含音訊檔與設定）。")
                        confirm_del_v = st.checkbox(
                            "確認刪除此音色角色庫",
                            key=f"chk_del_voice_{cur_voice}",
                        )
                        if st.button("🗑️ 確定刪除角色", key=f"btn_del_voice_{cur_voice}"):
                            if confirm_del_v:
                                delete_voice_profile(cur_voice)
                                st.success(f"已刪除發音人角色【{cur_voice}】！")
                                st.rerun()
                            else:
                                st.warning("請先勾選確認方塊。")

        with col_v2:
            st.markdown("### ➕ 建立新發音人角色 (OmniVoice)")
            st.markdown(
                "上傳一段 **5~15 秒無背景音樂**的清晰旁白音訊，並輸入完全對齊的逐字稿，即可透過 OmniVoice 逐句克隆該音色！"
            )
            new_v_raw_id = st.text_input(
                "音色英文 ID (例如: narrator_taiwan_male, host_anna)",
                placeholder="僅允許英數與下劃線",
                key="new_v_raw_id",
            )
            new_v_id = sanitize_id(new_v_raw_id)
            if new_v_raw_id and new_v_id != new_v_raw_id:
                st.caption(f"自動格式化 ID 為：`{new_v_id}`")

            new_v_name = st.text_input("角色顯示名稱", placeholder="例如：旁白・台灣中年男聲", key="new_v_name")
            new_v_mode = st.selectbox(
                "合成模式",
                options=["clone", "design"],
                format_func=lambda x: "聲音克隆 (Voice Clone - 推薦)" if x == "clone" else "語氣描述設計 (Voice Design)",
                key="new_v_mode",
            )
            new_v_wav = st.file_uploader(
                "上傳參考音訊 (WAV/MP3，5~15秒乾淨乾音)",
                type=["wav", "mp3"],
                key="new_v_wav",
            )
            new_v_txt = st.text_area(
                "參考音逐字稿 (字詞需與音訊內容 100% 吻合)",
                height=80,
                placeholder="例如：2012 年，美國國家偵察局突然打電話給 NASA...",
                key="new_v_txt",
            )
            col_nv1, col_nv2 = st.columns(2)
            with col_nv1:
                new_v_speed = st.slider("預設語速", min_value=0.5, max_value=2.0, value=1.0, step=0.05, key="new_v_speed")
            with col_nv2:
                new_v_temp = st.slider("預設位置溫度", min_value=0.0, max_value=1.0, value=0.1, step=0.05, key="new_v_temp")

            if st.button("✨ 建立新音色角色庫", type="primary", key="btn_create_voice"):
                if not new_v_id:
                    st.warning("請填寫音色 ID！")
                elif (REPO_ROOT / "assets" / "voices" / new_v_id).is_dir():
                    st.warning(f"音色角色【{new_v_id}】已存在，請更換 ID。")
                elif new_v_mode == "clone" and new_v_wav is None:
                    st.warning("克隆模式必須上傳參考音訊 (WAV/MP3)！")
                elif new_v_mode == "clone" and not new_v_txt.strip():
                    st.warning("克隆模式必須填寫參考音逐字稿！")
                else:
                    wav_data = new_v_wav.read() if new_v_wav is not None else None
                    save_voice_profile(
                        voice_id=new_v_id,
                        display_name=new_v_name or new_v_id,
                        mode=new_v_mode,
                        speed=new_v_speed,
                        position_temp=new_v_temp,
                        steps=32,
                        instruct="",
                        ref_text=new_v_txt,
                        wav_bytes=wav_data,
                    )
                    st.success(f"已成功建立發音人角色【{new_v_id}】！可立即在專案中使用。")
                    st.rerun()

    # ---------------------------------------------------------------------
    # SUBTAB 3: 畫面視覺風格管理 (Style)
    # ---------------------------------------------------------------------
    with subtab_style:
        col_s1, col_s2 = st.columns([1.2, 1])

        with col_s1:
            st.markdown("### 🎨 現有視覺風格管理")
            styles_dict = load_style_presets()
            style_keys = list(styles_dict.keys())

            if not style_keys:
                st.info("尚無可用視覺風格。")
            else:
                cur_style = st.selectbox(
                    "選擇要編輯的視覺風格",
                    options=style_keys,
                    format_func=lambda x: styles_dict.get(x, {}).get("name", x),
                    key="style_manage_select",
                )
                s_data = styles_dict.get(cur_style, {})

                cur_prev_rel = s_data.get("preview", "")
                cur_prev_p = REPO_ROOT / cur_prev_rel if cur_prev_rel and not cur_prev_rel.startswith("http") else None
                if cur_prev_p and cur_prev_p.is_file():
                    st.image(str(cur_prev_p), caption=f"【{s_data.get('name', cur_style)}】風格示範預覽", use_container_width=True)
                elif cur_prev_rel.startswith("http"):
                    st.image(cur_prev_rel, caption=f"【{s_data.get('name', cur_style)}】風格示範預覽", use_container_width=True)

                edit_s_name = st.text_input(
                    "風格顯示名稱",
                    value=s_data.get("name", cur_style),
                    key=f"sname_{cur_style}",
                )
                edit_s_desc = st.text_area(
                    "風格特色描述 (Description)",
                    value=s_data.get("description", ""),
                    height=70,
                    key=f"sdesc_{cur_style}",
                )
                edit_s_prefix = st.text_area(
                    "正向提示詞前綴 (Style Prefix - 作為出圖提示詞開頭，定義畫風與細節)",
                    value=s_data.get("prefix", ""),
                    height=120,
                    key=f"sprefix_{cur_style}",
                )
                edit_s_negative = st.text_area(
                    "負向提示詞 (Negative Prompt - 過濾畫面瑕疵)",
                    value=s_data.get("negative", ""),
                    height=80,
                    key=f"sneg_{cur_style}",
                )
                rep_s_img = st.file_uploader(
                    "替換風格示範預覽圖 (JPG/PNG)",
                    type=["jpg", "jpeg", "png"],
                    key=f"rep_simg_{cur_style}",
                )

                col_ss1, col_ss2 = st.columns([1, 1])
                with col_ss1:
                    if st.button("💾 儲存風格修改", key=f"btn_save_style_{cur_style}"):
                        saved_prev = s_data.get("preview", "")
                        if rep_s_img is not None:
                            img_dir = REPO_ROOT / "assets" / "styles" / "previews"
                            img_dir.mkdir(parents=True, exist_ok=True)
                            target_img = img_dir / f"{cur_style}.jpg"
                            target_img.write_bytes(rep_s_img.read())
                            saved_prev = f"assets/styles/previews/{cur_style}.jpg"
                        save_style_preset(
                            style_key=cur_style,
                            name=edit_s_name,
                            prefix=edit_s_prefix,
                            negative=edit_s_negative,
                            preview=saved_prev,
                            description=edit_s_desc,
                        )
                        st.success(f"已成功更新風格【{edit_s_name}】！")
                        st.rerun()

                with col_ss2:
                    with st.expander("🗑️ 刪除此視覺風格", expanded=False):
                        st.warning(f"即將從 assets/styles.yaml 移除風格「{s_data.get('name', cur_style)}」。")
                        confirm_del_s = st.checkbox(
                            "確認刪除此視覺風格",
                            key=f"chk_del_style_{cur_style}",
                        )
                        if st.button("🗑️ 確定刪除風格", key=f"btn_del_style_{cur_style}"):
                            if confirm_del_s:
                                delete_style_preset(cur_style)
                                st.success(f"已刪除風格【{cur_style}】！")
                                st.rerun()
                            else:
                                st.warning("請先勾選確認方塊。")

        with col_s2:
            st.markdown("### ➕ 新增自訂畫面視覺風格")
            st.markdown(
                "定義正向風格提示詞與負向過濾詞，建立後將永久保存在 `assets/styles.yaml`，並直接同步至建立新專案與分鏡生圖選單！"
            )
            new_s_raw_id = st.text_input(
                "風格英文 ID (例如: cyberpunk_neon, ghibli_watercolor)",
                placeholder="僅允許英數與下劃線",
                key="new_s_raw_id",
            )
            new_s_id = sanitize_id(new_s_raw_id)
            if new_s_raw_id and new_s_id != new_s_raw_id:
                st.caption(f"自動格式化 ID 為：`{new_s_id}`")

            new_s_name = st.text_input(
                "風格顯示名稱",
                placeholder="例如：賽博龐克霓虹風格 (Cyberpunk Neon)",
                key="new_s_name",
            )
            new_s_desc = st.text_area(
                "風格特色描述 (可選)",
                placeholder="簡短描述該畫風特點（如：光影、線條、氛圍等）",
                height=70,
                key="new_s_desc",
            )
            new_s_prefix = st.text_area(
                "正向提示詞前綴 (Style Prefix)",
                value="賽博龐克霓虹風格，雨夜高對比光影，金屬機械質感，電影感寬銀幕構圖，16:9 橫式構圖",
                height=110,
                key="new_s_prefix",
            )
            new_s_negative = st.text_area(
                "負向提示詞 (Negative Prompt)",
                value="文字浮水印、現代3D塑料感、低細節模糊、走形手部",
                height=80,
                key="new_s_negative",
            )
            new_s_img = st.file_uploader(
                "上傳風格示範預覽圖 (可選，JPG/PNG)",
                type=["jpg", "jpeg", "png"],
                key="new_s_img",
            )

            if st.button("✨ 建立新視覺風格", type="primary", key="btn_create_style"):
                if not new_s_id:
                    st.warning("請填寫風格 ID！")
                elif new_s_id in load_style_presets():
                    st.warning(f"風格 ID 【{new_s_id}】已存在，請更換名稱或直接在左側編輯。")
                else:
                    saved_prev = ""
                    if new_s_img is not None:
                        img_dir = REPO_ROOT / "assets" / "styles" / "previews"
                        img_dir.mkdir(parents=True, exist_ok=True)
                        target_img = img_dir / f"{new_s_id}.jpg"
                        target_img.write_bytes(new_s_img.read())
                        saved_prev = f"assets/styles/previews/{new_s_id}.jpg"

                    save_style_preset(
                        style_key=new_s_id,
                        name=new_s_name or new_s_id,
                        prefix=new_s_prefix,
                        negative=new_s_negative,
                        preview=saved_prev,
                        description=new_s_desc,
                    )
                    st.success(f"已成功建立視覺風格【{new_s_name or new_s_id}】！已同步至選單。")
                    st.rerun()

