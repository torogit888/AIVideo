"""流水線執行器、考據開關、系統環境、預設資產與 CLI 命令測試。"""

from __future__ import annotations

from pathlib import Path

import yaml

from aivideo.api.schemas import (
    CreateJobRequest,
    JobSummary,
    SceneDetail,
    SystemStatusResponse,
    UpdateJobRequest,
)
from aivideo.cli import build_parser
from aivideo.fonts import ASS_FONT_NAME, resolve_subtitle_font, subtitle_font_for_job
from aivideo.naming import (
    CONNECTION_LIGHTS,
    DEFAULT_USE_PIP,
    DEFAULT_VOICE_ID,
    STORYBOARD_GHOST_ACTIONS,
    STORYBOARD_OVERFLOW_ACTIONS,
    job_use_pip,
    primary_pipeline_action,
    script_workspace_mode,
    should_auto_pip,
    should_prompt_recut,
)
from aivideo.pipeline_runner import PipelineRunner
from aivideo.run_state import load_run_json, write_run_json

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_all_action_auto_pip_default():
    assert should_auto_pip("all") is True
    assert should_auto_pip("all", use_pip=False) is False
    assert should_auto_pip("images") is False
    assert should_auto_pip("tts") is False
    assert should_auto_pip("pip") is True


def test_all_action_respects_job_pip_switch():
    assert should_auto_pip("all") is True
    assert should_auto_pip("all", use_pip=False) is False
    assert should_auto_pip("all", use_pip=True) is True
    assert should_auto_pip("images", use_pip=True) is False
    assert should_auto_pip("pip", use_pip=False) is True
    assert DEFAULT_USE_PIP is True
    assert job_use_pip({}) is True
    assert job_use_pip({"use_pip": False}) is False
    assert job_use_pip({"use_pip": True}) is True


def test_schema_default_use_pip_on():
    assert CreateJobRequest.model_fields["use_pip"].default is True
    assert JobSummary.model_fields["use_pip"].default is True
    assert UpdateJobRequest.model_fields["use_pip"].default is None


def test_primary_button_follows_missing_assets():
    assert primary_pipeline_action(0, 0, 10, False)["action"] == "all"
    assert primary_pipeline_action(0, 0, 10, False)["label"] == "一鍵全流程"
    assert primary_pipeline_action(10, 3, 10, False)["action"] == "all"
    assert primary_pipeline_action(10, 3, 10, False)["label"] == "一鍵全流程"
    assert primary_pipeline_action(10, 10, 10, False)["action"] == "all"
    assert primary_pipeline_action(10, 10, 10, True, film_stale=True)["action"] == "all"
    assert primary_pipeline_action(10, 10, 10, True)["action"] == "preview"
    assert primary_pipeline_action(10, 10, 10, True)["label"] == "預覽成片"


def test_script_modes_and_command_bar():
    assert script_workspace_mode(None) == "new"
    assert script_workspace_mode("") == "new"
    assert script_workspace_mode("20261003_pepsi") == "edit"
    assert should_prompt_recut(True, True) is True
    assert should_prompt_recut(True, False) is False
    assert should_prompt_recut(False, True) is False
    assert STORYBOARD_GHOST_ACTIONS == ("images", "tts", "compose")
    assert "continuity" in STORYBOARD_OVERFLOW_ACTIONS
    assert "pip" in STORYBOARD_OVERFLOW_ACTIONS
    assert "force" in STORYBOARD_OVERFLOW_ACTIONS
    assert CONNECTION_LIGHTS == ("gemini", "comfy")


def test_run_json_roundtrip(tmp_path: Path):
    write_run_json(
        tmp_path,
        {
            "job_id": "j",
            "is_running": True,
            "is_paused": True,
            "scene_id": "001_shot_1",
            "progress": 0.4,
            "message": "暫停",
        },
    )
    data = load_run_json(tmp_path)
    assert data["is_paused"] is True
    assert data["scene_id"] == "001_shot_1"


def _write_pip_scene(
    job_dir: Path,
    name: str,
    *,
    enabled: bool,
    query: str,
    mode: str = "pip",
    image: bool = False,
    speech: bool = False,
    pip_png: bool = False,
) -> Path:
    scene = job_dir / "scenes" / name
    scene.mkdir(parents=True)
    (scene / "scene.yaml").write_text(
        yaml.safe_dump(
            {
                "id": name,
                "narration": "測試口白",
                "pip": {"enabled": enabled, "query": query, "mode": mode},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    if image:
        (scene / "image.png").write_bytes(b"png")
    if speech:
        (scene / "speech.wav").write_bytes(b"wav")
    if pip_png:
        (scene / "pip.png").write_bytes(b"pip")
    return scene


def test_auto_fetch_skips_scene_the_user_turned_off(tmp_path: Path, monkeypatch):
    from aivideo.auto_pip import auto_fetch_and_apply_pip

    job = tmp_path / "job"
    _write_pip_scene(job, "001_shot_1", enabled=True, query="Hubble")
    _write_pip_scene(job, "002_shot_2", enabled=False, query="Pepsi")
    called: list[str] = []

    def fake_fetch(scene_dir: Path, query=None, media_type="auto"):
        called.append(scene_dir.name)
        return True

    monkeypatch.setattr("aivideo.auto_pip.fetch_single_scene_pip", fake_fetch)
    monkeypatch.setattr(
        "aivideo.auto_pip.auto_detect_scene_reference_entities",
        lambda job_dir: (_ for _ in ()).throw(AssertionError("已有考據詞時不該重判")),
    )

    assert auto_fetch_and_apply_pip(job) == 1
    assert called == ["001_shot_1"]
    off = yaml.safe_load((job / "scenes" / "002_shot_2" / "scene.yaml").read_text(encoding="utf-8"))
    assert off["pip"]["enabled"] is False
    assert off["pip"]["query"] == "Pepsi"


def test_backfill_does_not_reopen_a_scene_switch(tmp_path: Path, monkeypatch):
    from aivideo.auto_pip import backfill_missing_pip_queries

    job = tmp_path / "job"
    bare = job / "scenes" / "001_shot_1"
    off = job / "scenes" / "002_shot_2"
    bare.mkdir(parents=True)
    off.mkdir(parents=True)
    (bare / "scene.yaml").write_text(
        yaml.safe_dump({"id": "001_shot_1", "narration": "哈伯"}),
        encoding="utf-8",
    )
    (off / "scene.yaml").write_text(
        yaml.safe_dump({"id": "002_shot_2", "narration": "百事", "pip": {"enabled": False}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "aivideo.auto_pip.auto_detect_scene_reference_entities",
        lambda job_dir: {"001_shot_1": "Hubble", "002_shot_2": "Pepsi"},
    )

    assert backfill_missing_pip_queries(job) == 2
    bare_cfg = yaml.safe_load((bare / "scene.yaml").read_text(encoding="utf-8"))
    off_cfg = yaml.safe_load((off / "scene.yaml").read_text(encoding="utf-8"))
    assert bare_cfg["pip"]["enabled"] is True
    assert bare_cfg["pip"]["query"] == "Hubble"
    assert off_cfg["pip"]["enabled"] is False
    assert off_cfg["pip"]["query"] == "Pepsi"


def test_all_mode_respects_scene_pip_switch(tmp_path: Path, monkeypatch):
    job = tmp_path / "20261025_pip_switch"
    _write_pip_scene(job, "001_shot_1", enabled=True, query="Hubble", image=True, speech=True)
    _write_pip_scene(job, "002_shot_2", enabled=False, query="Pepsi", image=True, speech=True)
    called: list[str] = []
    monkeypatch.setattr("aivideo.pipeline_runner.run_images", lambda *a, **k: 0)
    monkeypatch.setattr("aivideo.pipeline_runner.run_tts", lambda *a, **k: 0)
    monkeypatch.setattr("aivideo.pipeline_runner.run_compose", lambda *a, **k: 0)
    monkeypatch.setattr("aivideo.pipeline_runner.generate_preview_html", lambda *a, **k: None)

    def fake_fetch(scene_dir: Path, query=None, media_type="auto"):
        called.append(scene_dir.name)
        return True

    monkeypatch.setattr("aivideo.auto_pip.fetch_single_scene_pip", fake_fetch)
    runner = PipelineRunner(job.name, job)
    runner._run_worker(mode="all", skip_done=True, auto_pip=True, pause_between_stages=False)

    assert called == ["001_shot_1"]
    off = yaml.safe_load((job / "scenes" / "002_shot_2" / "scene.yaml").read_text(encoding="utf-8"))
    assert off["pip"]["enabled"] is False


def test_disabled_spotlight_still_asks_for_an_image(tmp_path: Path, monkeypatch):
    job = tmp_path / "20261025_spot_off"
    scene = _write_pip_scene(
        job,
        "001_shot_1",
        enabled=False,
        query="Hubble",
        mode="spotlight",
        speech=True,
        pip_png=True,
    )
    images: list[str] = []
    monkeypatch.setattr(
        "aivideo.pipeline_runner.run_images",
        lambda *a, **k: images.append("img") or 0,
    )
    monkeypatch.setattr("aivideo.pipeline_runner.run_tts", lambda *a, **k: 0)
    monkeypatch.setattr("aivideo.pipeline_runner.run_compose", lambda *a, **k: 0)
    monkeypatch.setattr("aivideo.pipeline_runner.generate_preview_html", lambda *a, **k: None)
    monkeypatch.setattr(
        "aivideo.auto_pip.fetch_single_scene_pip",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("關掉的幕不該下載")),
    )
    runner = PipelineRunner(job.name, job)
    runner._run_worker(mode="all", skip_done=True, auto_pip=True, pause_between_stages=False)

    assert images == ["img"]
    cfg = yaml.safe_load((scene / "scene.yaml").read_text(encoding="utf-8"))
    assert cfg["pip"]["enabled"] is False


def test_pipeline_runner_emits_notice_seq_on_compose_failure(tmp_path: Path):
    job_dir = tmp_path / "20261024_fail_once"
    s1 = job_dir / "scenes" / "001_shot_1"
    s1.mkdir(parents=True)
    runner = PipelineRunner(job_dir.name, job_dir)
    runner._run_worker(mode="compose", skip_done=True, auto_pip=False, pause_between_stages=False)
    assert runner.error_msg is not None
    assert runner.notice_seq >= 1


def test_default_voice_matches_disk():
    voices = [p.name for p in (REPO_ROOT / "assets" / "voices").iterdir() if p.is_dir()]
    assert DEFAULT_VOICE_ID in voices
    assert CreateJobRequest.model_fields["voice_id"].default == DEFAULT_VOICE_ID
    assert JobSummary.model_fields["voice_id"].default == DEFAULT_VOICE_ID
    assert DEFAULT_VOICE_ID != "female01"


def test_code_defaults_have_no_female01():
    schema = (REPO_ROOT / "aivideo" / "api" / "schemas.py").read_text(encoding="utf-8")
    assert 'voice_id: str = "female01"' not in schema
    naming = (REPO_ROOT / "aivideo" / "naming.py").read_text(encoding="utf-8")
    assert '"female01"' not in naming


def test_system_status_has_gemini_and_comfy_lights():
    fields = SystemStatusResponse.model_fields
    assert "gemini_configured" in fields
    assert "comfyui_online" in fields
    assert "takes" in SceneDetail.model_fields


def test_cli_has_lock_unlock_select_gc_and_no_unimplemented_stubs():
    parser = build_parser()
    names = []
    for action in parser._subparsers._actions:
        if getattr(action, "choices", None):
            names.extend(action.choices.keys())
    assert "lock" in names
    assert "unlock" in names
    assert "select" in names
    assert "gc" in names
    for unimpl in ("parse", "run", "regen"):
        assert unimpl not in names
    help_lock = parser.parse_args(["lock", "--job", "jobs/x", "--scene", "001", "--image"])
    assert help_lock.func.__name__ == "run_lock"


def test_font_resolver_has_ass_name():
    info = resolve_subtitle_font()
    assert info["font_name"] == ASS_FONT_NAME
    path = subtitle_font_for_job()
    assert path
    readme = (REPO_ROOT / "assets" / "fonts" / "README.md").read_text(encoding="utf-8")
    assert "Noto" in readme


def test_tones_readme_matches_disk():
    tones_dir = REPO_ROOT / "assets" / "tones"
    on_disk = sorted(p.stem for p in tones_dir.glob("*.md") if p.name.lower() != "readme.md")
    readme = (tones_dir / "README.md").read_text(encoding="utf-8")
    for name in on_disk:
        assert f"{name}.md" in readme
    assert "tech_business_deepdive.md" not in readme
    assert "suspense_noir.md" not in readme


def test_all_mode_runs_pip_images_tts_and_compose_in_order(tmp_path: Path, monkeypatch):
    job = tmp_path / "20261027_full_order"
    _write_pip_scene(job, "001_shot_1", enabled=True, query="Hubble", mode="pip", image=False, speech=False)

    order: list[str] = []

    def fake_images(args, *a, **k):
        order.append("images")
        (job / "scenes" / "001_shot_1" / "image.png").write_bytes(b"img")
        return 0

    def fake_pip(scene_dir: Path, query=None, media_type="auto"):
        order.append("pip")
        (scene_dir / "pip.png").write_bytes(b"pip")
        return True

    def fake_tts(args, *a, **k):
        order.append("tts")
        (job / "scenes" / "001_shot_1" / "speech.wav").write_bytes(b"wav")
        return 0

    def fake_compose(args, *a, **k):
        order.append("compose")
        return 0

    monkeypatch.setattr("aivideo.pipeline_runner.run_images", fake_images)
    monkeypatch.setattr("aivideo.auto_pip.fetch_single_scene_pip", fake_pip)
    monkeypatch.setattr("aivideo.pipeline_runner.run_tts", fake_tts)
    monkeypatch.setattr("aivideo.pipeline_runner.run_compose", fake_compose)
    monkeypatch.setattr("aivideo.pipeline_runner.generate_preview_html", lambda *a, **k: None)

    runner = PipelineRunner(job.name, job)
    runner._run_worker(mode="all", skip_done=True, auto_pip=True, pause_between_stages=False)

    # 確保單幕順序為「出圖與考據(images+pip) -> 出聲(tts) -> 合成影片(compose)」
    assert set(order[:2]) == {"images", "pip"}
    assert order[2:] == ["tts", "compose"]


def test_failed_pip_records_rejected_candidates_and_reason(tmp_path: Path, monkeypatch):
    from io import BytesIO
    from PIL import Image
    from aivideo.auto_pip import fetch_single_scene_pip
    from aivideo.api.routes import scenes as scenes_route

    monkeypatch.setattr(scenes_route, "JOBS_DIR", tmp_path)
    job = tmp_path / "20261027_pip_reject"
    s1 = _write_pip_scene(job, "001_shot_1", enabled=True, query="Moscow Expo 1959", mode="pip")

    buf = BytesIO()
    Image.new("RGB", (400, 300), color=(120, 40, 40)).save(buf, format="JPEG")
    fake_img_bytes = buf.getvalue()

    monkeypatch.setattr(
        "aivideo.auto_pip.search_all_source_candidates",
        lambda q, limit=6: [
            {
                "title": "Battle of Moscow 1941 soldiers",
                "url": "https://example.org/moscow_1941.jpg",
                "source": "維基共享資源 (Wikimedia)",
                "width": 800,
                "height": 600,
                "media_type": "image",
            }
        ],
    )
    monkeypatch.setattr("aivideo.auto_pip._download_image_bytes", lambda url: fake_img_bytes)
    monkeypatch.setattr(
        "aivideo.auto_pip.verify_pip_match_with_ai",
        lambda **kw: {
            "passed": False,
            "confidence": 0.1,
            "reason": "畫面為1941年二戰莫斯科戰役士兵，與1959年博覽會無關",
        },
    )

    ok = fetch_single_scene_pip(s1, "Moscow Expo 1959", media_type="image")
    assert ok is False
    assert (s1 / "pip_rejected.png").is_file()

    summaries = scenes_route.list_scenes(job.name)
    assert len(summaries) == 1
    item = summaries[0]
    assert item.pip_error is not None
    assert "1941" in item.pip_error
    assert len(item.pip_rejected) == 1
    assert item.pip_rejected[0].title == "Battle of Moscow 1941 soldiers"
    assert "1941" in (item.pip_rejected[0].reason or "")
    assert item.status.pip_rejected_url is not None


def test_progressive_pip_queries_and_wikipedia_relevance():
    from aivideo.auto_pip import build_progressive_search_queries, is_wikipedia_title_relevant

    q = "Post-war British food rationing queue 1951"
    variants = build_progressive_search_queries(q)
    assert q in variants
    assert any("British food rationing" in v for v in variants)
    assert is_wikipedia_title_relevant(q, "Rationing in the United Kingdom") is True
    assert is_wikipedia_title_relevant("Moscow street", "Battle of Moscow") is False
    assert is_wikipedia_title_relevant("Hugh Beaver", "List of people from London") is False


def test_google_image_parser_extracts_candidates(monkeypatch):
    from aivideo.auto_pip import search_google_image

    fake_html = (
        'AF_initDataCallback({data:[["https://encrypted-tbn0.gstatic.com/images?q\\u003dtbn:ANd9GcTest",180,240],'
        '["https://example.org/history/british_rationing_1951.jpg",800,1200],'
        '"2003":[null,"id1","https://example.org/article","Post-war British food rationing queue 1951"]]});'
    )

    class _FakeResp:
        status_code = 200
        text = fake_html

    monkeypatch.setattr("aivideo.auto_pip.requests.get", lambda *a, **k: _FakeResp())
    res = search_google_image("Post-war British food rationing queue 1951")
    assert len(res) == 1
    assert res[0]["url"] == "https://example.org/history/british_rationing_1951.jpg"
    assert res[0]["source"] == "Google 圖片 (Google Images)"
    assert "rationing" in str(res[0]["title"]).lower()


def test_ai_pip_plans_and_youtube_video_search(tmp_path: Path, monkeypatch):
    import json as json_mod
    from aivideo.auto_pip import fetch_single_scene_pip, search_youtube_video
    from aivideo.scene_cut import apply_scene_cut

    # 1. 驗證 search_youtube_video 能解析 yt-dlp ytsearch JSON 行並過濾過長影片
    fake_yt_stdout = "\n".join(
        [
            json_mod.dumps(
                {
                    "id": "IaTCGAxJ564",
                    "title": "END OF RATIONING 1954 British Pathe",
                    "duration": 60,
                    "thumbnails": [{"url": "https://i.ytimg.com/vi/IaTCGAxJ564/hqdefault.jpg"}],
                }
            ),
            json_mod.dumps(
                {
                    "id": "too_long_vid",
                    "title": "3 Hour Full Stream",
                    "duration": 10800,
                }
            ),
        ]
    )

    class _FakeProc:
        returncode = 0
        stdout = fake_yt_stdout

    monkeypatch.setattr("aivideo.auto_pip.shutil.which", lambda cmd: "/usr/local/bin/yt-dlp")
    monkeypatch.setattr("aivideo.auto_pip.subprocess.run", lambda *a, **k: _FakeProc())

    yt_cands = search_youtube_video("British food rationing", limit=3)
    assert len(yt_cands) == 1
    assert yt_cands[0]["url"] == "https://www.youtube.com/watch?v=IaTCGAxJ564"
    assert yt_cands[0]["media_type"] == "video"
    assert "YouTube" in str(yt_cands[0]["source"])

    # 2. 驗證 AI 判定的 pip_media_type="video" / pip_mode="broll" 會寫入 scene.yaml，且不需命中寫死關鍵字即優先抓影片
    apply_scene_cut(
        tmp_path,
        [
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "賽跑衝線",
                "narration": "羅傑班尼斯特衝過終點線打破四分鐘一英里紀錄，",
                "image_prompt": "runner crossing finish line",
                "pip_query": "Roger Bannister four minute mile 1954",
                "pip_media_type": "video",
                "pip_mode": "broll",
            }
        ],
        clear_existing=True,
    )
    s1 = tmp_path / "scenes" / "001_shot_1"
    cfg = yaml.safe_load((s1 / "scene.yaml").read_text(encoding="utf-8"))
    assert cfg["pip"]["media_type"] == "video"
    assert cfg["pip"]["mode"] == "broll"

    video_searched: list[str] = []
    monkeypatch.setattr(
        "aivideo.auto_pip.search_all_source_video_candidates",
        lambda q, limit=5: video_searched.append(q) or [],
    )
    monkeypatch.setattr("aivideo.auto_pip.search_all_source_candidates", lambda q, limit=6: [])

    fetch_single_scene_pip(s1)
    assert video_searched == ["Roger Bannister four minute mile 1954"]




