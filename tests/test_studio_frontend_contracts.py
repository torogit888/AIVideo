"""Studio 前後端契約、靜態媒體掛載安全、元件拆分與狀態同步測試。"""

from __future__ import annotations

from pathlib import Path

from aivideo.media import media_mounts, media_url_allowed, spa_dist_dir

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_removed_and_studio_ports():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "streamlit" not in pyproject
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "8501" not in compose
    assert "8000" in compose
    assert not (REPO_ROOT / "aivideo" / "webui.py").exists()
    assert not (REPO_ROOT / "aivideo" / "__pycache__" / "webui.cpython-37.pyc").exists()
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "5173" in readme
    assert "8000" in readme
    assert "uvicorn" in readme


def test_media_mounts_do_not_expose_repo_root():
    mounts = media_mounts(REPO_ROOT)
    urls = [u for u, _ in mounts]
    assert "/media/jobs" in urls
    assert "/media/assets/voices" in urls
    assert media_url_allowed("/media/jobs/x/scenes/001/image.png")
    assert media_url_allowed("/media/assets/voices/tw_female01/preview.wav")
    assert not media_url_allowed("/media/assets/credentials/client_secret.json")
    assert not media_url_allowed("/media/aivideo/cli.py")
    dist = spa_dist_dir(REPO_ROOT)
    assert dist is None or (dist / "index.html").is_file()


def test_spa_dist_helper():
    assert spa_dist_dir(REPO_ROOT) is None or (REPO_ROOT / "web" / "dist" / "index.html").is_file()
    app_py = (REPO_ROOT / "aivideo" / "api" / "app.py").read_text(encoding="utf-8")
    assert "spa_dist_dir" in app_py


def test_frontend_script_and_storyboard_contracts():
    ts = (REPO_ROOT / "web" / "src" / "studioActions.ts").read_text(encoding="utf-8")
    assert "scriptWorkspaceMode" in ts
    assert "STORYBOARD_GHOST_ACTIONS" in ts
    assert "DEFAULT_USE_PIP" in ts
    assert 'DEFAULT_CUSTOM_PROMPT = "開頭: 大家好~我是白兔!"' in ts
    editor = (REPO_ROOT / "web" / "src" / "components" / "ScriptEditor.tsx").read_text(encoding="utf-8")
    assert "美國太空總署羅曼太空望遠鏡" not in editor
    assert "故事要求" in editor
    assert "DEFAULT_CUSTOM_PROMPT" in editor
    assert "draftResetKey" in editor
    store = (REPO_ROOT / "web" / "src" / "store.ts").read_text(encoding="utf-8")
    assert "draftResetKey" in store
    assert 'removeItem("aivideo_draft_custom_prompt")' in store
    assert 'removeItem("aivideo_draft_outline")' in store
    rail = (REPO_ROOT / "web" / "src" / "components" / "SidebarRail.tsx").read_text(encoding="utf-8")
    assert "AI_TEXT_MODELS" not in rail
    assert "AI_IMAGE_MODELS" not in rail
    assert "selectJob" not in rail
    grid = (REPO_ROOT / "web" / "src" / "components" / "StoryboardGrid.tsx").read_text(encoding="utf-8")
    assert "清空圖片" not in grid
    assert "考據 (PiP)" not in grid
    assert "視覺一致性" not in grid or "尚未定裝" in grid


def test_frontend_pipeline_and_media_contracts():
    app = (REPO_ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    settings = (REPO_ROOT / "web" / "src" / "components" / "SettingsPanel.tsx").read_text(encoding="utf-8")
    assert "patchSceneCard" in app
    assert "檢測 Gemini" in settings
    topbar = (REPO_ROOT / "web" / "src" / "components" / "Topbar.tsx").read_text(encoding="utf-8")
    assert "pausePipeline" in topbar
    assert "暫停" in topbar
    grid = (REPO_ROOT / "web" / "src" / "components" / "StoryboardGrid.tsx").read_text(encoding="utf-8")
    assert "act_index" in grid
    assert "大綱" in grid
    pipeline = (REPO_ROOT / "aivideo" / "api" / "routes" / "pipeline.py").read_text(encoding="utf-8")
    assert 'prefix="/pause"' in pipeline or "/pause" in pipeline
    app_py = (REPO_ROOT / "aivideo" / "api" / "app.py").read_text(encoding="utf-8")
    assert "media_mounts" in app_py
    assert "StaticFiles(directory=str(REPO_ROOT))" not in app_py


def test_frontend_inspector_and_settings_contracts():
    inspector = (REPO_ROOT / "web" / "src" / "components" / "SceneInspector.tsx").read_text(encoding="utf-8")
    assert "handleToggleLock" in inspector
    assert "gcSceneTakes" in inspector
    assert "畫面已鎖" in inspector
    settings = (REPO_ROOT / "web" / "src" / "components" / "SettingsPanel.tsx").read_text(encoding="utf-8")
    assert "檢測 Gemini" in settings
    assert "預設發音人" in settings
    assert "font_ok" in settings


def test_frontend_sse_dedup_and_inspector_tab_visibility():
    app_tsx = (REPO_ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert '(currentTab === "storyboard" || currentTab === "film") && <SceneInspector />' in app_tsx
    assert "lastShownErrorKey" in app_tsx

    store_ts = (REPO_ROOT / "web" / "src" / "store.ts").read_text(encoding="utf-8")
    assert "set({ currentTab: tab, isInspectorOpen: false })" in store_ts

    film_tsx = (REPO_ROOT / "web" / "src" / "components" / "FilmViewer.tsx").read_text(encoding="utf-8")
    assert "film_mtime" in film_tsx
    assert "filmResumeSec" in film_tsx
    assert 'setTab("storyboard")' not in film_tsx
    assert "openInspector(sceneId)" in film_tsx
    assert "invisible" in app_tsx

    topbar_tsx = (REPO_ROOT / "web" / "src" / "components" / "Topbar.tsx").read_text(encoding="utf-8")
    assert "primaryPipelineAction" in topbar_tsx

    editor_tsx = (REPO_ROOT / "web" / "src" / "components" / "ScriptEditor.tsx").read_text(encoding="utf-8")
    assert "hasScenes && anchorsReanalyzed" in editor_tsx


def test_frontend_pip_persistence_and_pacing_sync():
    inspector = (REPO_ROOT / "web" / "src" / "components" / "SceneInspector.tsx").read_text(encoding="utf-8")
    assert 'handleQuickUpdatePip(pipEnabled, pipMode, "已更新考據卡片大小"' in inspector
    assert 'handleQuickUpdatePip(pipEnabled, pipMode, "已更新考據疊加位置"' in inspector

    editor = (REPO_ROOT / "web" / "src" / "components" / "ScriptEditor.tsx").read_text(encoding="utf-8")
    assert "detail.config?.visual_pacing" in editor
    assert "wordCount" in editor


def test_frontend_shared_store_and_duration_estimator():
    actions_ts = (REPO_ROOT / "web" / "src" / "studioActions.ts").read_text(encoding="utf-8")
    assert "export function estimateJobDuration" in actions_ts
    assert "export function formatDurationClock" in actions_ts

    store_ts = (REPO_ROOT / "web" / "src" / "store.ts").read_text(encoding="utf-8")
    assert "burnSubtitles:" in store_ts
    assert "isContinuityOpen:" in store_ts
    assert "anchorsRevision:" in store_ts

    topbar = (REPO_ROOT / "web" / "src" / "components" / "Topbar.tsx").read_text(encoding="utf-8")
    grid = (REPO_ROOT / "web" / "src" / "components" / "StoryboardGrid.tsx").read_text(encoding="utf-8")
    editor = (REPO_ROOT / "web" / "src" / "components" / "ScriptEditor.tsx").read_text(encoding="utf-8")
    modal = (REPO_ROOT / "web" / "src" / "components" / "VisualContinuityModal.tsx").read_text(encoding="utf-8")

    for content in (topbar, grid, editor, modal):
        assert 'CustomEvent("aivideo:' not in content

    assert "estimateJobDuration" in topbar
    assert "estimateJobDuration" in grid

    inspector = (REPO_ROOT / "web" / "src" / "components" / "SceneInspector.tsx").read_text(encoding="utf-8")
    assert "liveImageUrl" in inspector
    assert 'value="broll"' in inspector


def test_app_component_split_into_focused_panels():
    comp_dir = REPO_ROOT / "web" / "src" / "components"
    assert (comp_dir / "OverviewPanel.tsx").is_file()
    assert (comp_dir / "SettingsPanel.tsx").is_file()
    assert (comp_dir / "StudioConfirmModal.tsx").is_file()

    app_text = (REPO_ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "<OverviewPanel" in app_text
    assert "<SettingsPanel" in app_text
    assert "<StudioConfirmModal" in app_text
    assert len(app_text.splitlines()) < 300


def test_shared_delete_job_and_backend_hygiene():
    store_ts = (REPO_ROOT / "web" / "src" / "store.ts").read_text(encoding="utf-8")
    topbar_tsx = (REPO_ROOT / "web" / "src" / "components" / "Topbar.tsx").read_text(encoding="utf-8")
    overview_tsx = (REPO_ROOT / "web" / "src" / "components" / "OverviewPanel.tsx").read_text(encoding="utf-8")
    editor_tsx = (REPO_ROOT / "web" / "src" / "components" / "ScriptEditor.tsx").read_text(encoding="utf-8")
    api_ts = (REPO_ROOT / "web" / "src" / "api.ts").read_text(encoding="utf-8")

    assert "deleteJob: async" in store_ts
    assert "await deleteJob(" in topbar_tsx
    assert "await deleteJob(" in overview_tsx
    assert "api.deleteJob" not in topbar_tsx
    assert "api.deleteJob" not in overview_tsx
    assert "({currentStyleObj.id})" not in editor_tsx
    assert "metaphor_style" not in api_ts
    assert "lines_per_scene" not in api_ts

    app_py = (REPO_ROOT / "aivideo" / "api" / "app.py").read_text(encoding="utf-8")
    assert "allow_credentials=False" in app_py

    for rel in ("aivideo/naming.py", "aivideo/api/routes/jobs.py", "aivideo/api/routes/scenes.py"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "audio.wav" not in text

