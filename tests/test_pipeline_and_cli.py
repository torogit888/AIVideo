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
    assert primary_pipeline_action(0, 0, 10, False)["action"] == "images"
    assert primary_pipeline_action(0, 0, 10, False)["label"] == "生成未完成畫面"
    assert primary_pipeline_action(10, 3, 10, False)["action"] == "tts"
    assert primary_pipeline_action(10, 3, 10, False)["label"] == "生成配音"
    assert primary_pipeline_action(10, 10, 10, False)["action"] == "compose"
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
