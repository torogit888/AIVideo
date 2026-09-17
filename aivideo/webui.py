from __future__ import annotations

import json
import os
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
from aivideo.story_generator import (
    STYLE_PRESETS,
    create_job_bundle,
    generate_story_script,
    parse_script_lines_to_scenes,
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
selected_job_name = st.sidebar.selectbox(
    "📁 選擇當前專案 (Job)",
    options=jobs_list if jobs_list else ["無專案"],
    index=0 if jobs_list else 0,
)

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
        word_count_slider = st.select_slider(
            "📏 需求字數規模",
            options=[800, 1500, 2500, 4000],
            value=1500,
            help="4000字約對應 12~15 分鐘完整專題；1500字約對應 5~6 分鐘精華專題。",
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
        selected_style = st.selectbox(
            "🎨 選擇畫面視覺風格 (Style)",
            options=list(STYLE_PRESETS.keys()),
            index=0,
            format_func=lambda x: STYLE_PRESETS[x]["name"],
        )
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

    script_text = st.text_area(
        "📝 口白腳本編輯區（每行一句台詞，支援線上修訂）",
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

    if st.button("✨ 將上方腳本正式建立為新專案 (Create Job)"):
        if not script_text.strip():
            st.warning("請先生成或在文字框輸入腳本台詞！")
        else:
            with st.spinner("正在切分場景並建立專案結構..."):
                scenes = parse_script_lines_to_scenes(
                    script_text,
                    sentences_per_scene=sents_per_scene,
                    style_key=selected_style,
                )
                job_dir = create_job_bundle(
                    job_id=job_slug_input,
                    title=topic_input,
                    scenes=scenes,
                    style_key=selected_style,
                    voice_id=selected_voice,
                )
                st.success(f"已成功建立專案！共切分出 {len(scenes)} 個場景分鏡。\n路徑：{job_dir.relative_to(REPO_ROOT)}")
                st.info("請切換至「🎞️ 分鏡看板與生成」分頁開始批次出圖與語音合成！")


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

            # 頂部快捷操作按鈕組
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)

            class CmdArgs:
                def __init__(self, job, force=False, scene=None, count=1, draft=False, new_seed=False, keep_seed=False):
                    self.job = str(job)
                    self.force = force
                    self.scene = scene
                    self.count = count
                    self.draft = draft
                    self.new_seed = new_seed
                    self.keep_seed = keep_seed

            with col_b1:
                if st.button("🎨 批次出圖 (Images)"):
                    with st.spinner("正在呼叫 Gemini API 產生 16:9 畫面..."):
                        res = run_images(CmdArgs(job_path, force=True))
                        st.rerun()

            with col_b2:
                if st.button("🎙️ 批次配音 (Voice Clone)"):
                    with st.spinner("正在透過 ComfyUI 進行逐句聲音克隆合成..."):
                        res = run_tts(CmdArgs(job_path, force=True))
                        st.rerun()

            with col_b3:
                if st.button("🎬 合成 1080p 成片 (Compose)"):
                    with st.spinner("正在透過 FFmpeg 合成 Ken Burns 推鏡與 1080p ASS 字幕..."):
                        run_compose(CmdArgs(job_path))
                        generate_preview_html(job_path)
                        st.success("成片合成完成！請切換到「📺 1080p 成片預覽」分頁播放！")

            with col_b4:
                if st.button("🚀 全流程一鍵重新生成 (All-in-One)", type="primary"):
                    with st.spinner("正在依序執行出圖、配音與成片合成..."):
                        run_images(CmdArgs(job_path, force=True))
                        run_tts(CmdArgs(job_path, force=True))
                        run_compose(CmdArgs(job_path))
                        generate_preview_html(job_path)
                        st.success("全流程重新生成大功告成！")
                        st.rerun()

            st.markdown("---")
            st.markdown("### 🎞️ 分鏡看板 (Storyboard)")

            scenes_dir = job_path / "scenes"
            scene_dirs = sorted([p for p in scenes_dir.iterdir() if p.is_dir()]) if scenes_dir.is_dir() else []

            for s_dir in scene_dirs:
                s_id = s_dir.name
                s_yaml_p = s_dir / "scene.yaml"
                if not s_yaml_p.is_file():
                    continue
                with open(s_yaml_p, "r", encoding="utf-8") as f:
                    scfg = yaml.safe_load(f) or {}

                img_p = s_dir / "image.png"
                wav_p = s_dir / "speech.wav"
                speech_j = s_dir / "speech.json"

                dur_str = "—"
                if speech_j.is_file():
                    try:
                        dur_str = f"{json.loads(speech_j.read_text(encoding='utf-8')).get('duration_sec', '—')}s"
                    except Exception:
                        pass

                with st.expander(f"【{s_id}】{scfg.get('title', s_id)}（時長: {dur_str}）", expanded=True):
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
                                with st.spinner("重新呼叫 Gemini 抽圖中..."):
                                    run_images(CmdArgs(job_path, scene=s_id, force=True, new_seed=True))
                                    st.rerun()
                        with btn_c2:
                            if st.button(f"🎙️ 重錄這段聲音", key=f"btn_tts_{s_id}"):
                                with st.spinner("重新呼叫 ComfyUI 克隆語音中..."):
                                    run_tts(CmdArgs(job_path, scene=s_id, force=True))
                                    st.rerun()

                    with scol2:
                        st.markdown("**旁白台詞：**")
                        st.write(scfg.get("narration", ""))
                        st.markdown("**畫面提示詞 (Prompt)：**")
                        st.code(scfg.get("image_prompt", ""), language="text")


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
    st.markdown('<div class="main-header">發音人角色庫與語氣風格庫</div>', unsafe_allow_html=True)

    col_a1, col_a2 = st.columns([1, 1])

    with col_a1:
        st.markdown("### 🎙️ 音色角色庫 (Voice Personas)")
        voices_dir = REPO_ROOT / "assets" / "voices"
        for v_name in get_available_voices():
            v_dir = voices_dir / v_name
            vyaml_p = v_dir / "voice.yaml"
            vwav_p = v_dir / "reference.wav"
            vtxt_p = v_dir / "reference.txt"

            vcfg = {}
            if vyaml_p.is_file():
                try:
                    vcfg = yaml.safe_load(vyaml_p.read_text(encoding="utf-8")) or {}
                except Exception:
                    pass

            with st.container():
                st.markdown(f"**【{v_name}】** · {vcfg.get('display_name', v_name)} `(模式: {vcfg.get('mode', 'clone')})`")
                if vwav_p.is_file():
                    st.audio(str(vwav_p))
                if vtxt_p.is_file():
                    st.caption(f"逐字稿: {vtxt_p.read_text(encoding='utf-8').strip()}")
                st.markdown("---")

    with col_a2:
        st.markdown("### 🎭 口吻語氣庫 (Story Tones)")
        tones_dir = REPO_ROOT / "assets" / "tones"
        for t_name in get_available_tones().keys():
            t_file = tones_dir / f"{t_name}.md"
            with st.container():
                st.markdown(f"**【{t_name}】**")
                content = t_file.read_text(encoding="utf-8")
                st.text_area(f"{t_name} 範本內容", value=content[:500] + ("..." if len(content) > 500 else ""), height=150, key=f"tone_box_{t_name}")
