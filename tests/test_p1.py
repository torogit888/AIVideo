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
from aivideo.naming import (
    CONNECTION_LIGHTS,
    DEFAULT_USE_PIP,
    STORYBOARD_GHOST_ACTIONS,
    STORYBOARD_OVERFLOW_ACTIONS,
    job_use_pip,
    script_workspace_mode,
    should_auto_pip,
    should_prompt_recut,
)
from aivideo.scene_cut import apply_scene_cut
from aivideo.takes import list_scene_takes, select_current_take
from aivideo.story_generator import create_job_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_all_action_respects_job_pip_switch():
    assert should_auto_pip("all") is False
    assert should_auto_pip("all", use_pip=False) is False
    assert should_auto_pip("all", use_pip=True) is True
    assert should_auto_pip("images", use_pip=True) is False
    assert should_auto_pip("pip", use_pip=False) is True
    assert DEFAULT_USE_PIP is False
    assert job_use_pip({}) is False
    assert job_use_pip({"use_pip": True}) is True


def test_schema_default_use_pip_off():
    assert CreateJobRequest.model_fields["use_pip"].default is False
    assert JobSummary.model_fields["use_pip"].default is False
    assert UpdateJobRequest.model_fields["use_pip"].default is None


def test_new_job_bundle_writes_use_pip_false(tmp_path: Path, monkeypatch):
    import aivideo.story_generator as sg

    monkeypatch.setattr(sg, "REPO_ROOT", tmp_path)
    job_dir = create_job_bundle(
        job_id="20261004_p1",
        title="測試",
        scenes=[
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "開場",
                "narration": "你敢相信這件事",
                "image_prompt": "wide shot",
            }
        ],
    )
    cfg = yaml.safe_load((job_dir / "job.yaml").read_text(encoding="utf-8"))
    assert cfg["use_pip"] is False


def test_list_and_select_takes(tmp_path: Path):
    scene = tmp_path / "scenes" / "001_shot_1"
    takes = scene / "takes"
    takes.mkdir(parents=True)
    (takes / "image_20261003T120000.png").write_bytes(b"old")
    (takes / "image_20261003T130000.png").write_bytes(b"new")
    (takes / "speech_20261003T120000.wav").write_bytes(b"wav-a")
    (takes / "speech_20261003T120000_sent_1.wav").write_bytes(b"skip")
    (takes / "speech_20261003T120000_silence.wav").write_bytes(b"skip")
    (scene / "scene.yaml").write_text(
        yaml.safe_dump({"id": "001_shot_1", "current": {"image_take": None, "speech_take": None}}),
        encoding="utf-8",
    )

    listed = list_scene_takes(scene, job_id="job", scene_id="001_shot_1")
    assert [t["take_id"] for t in listed["images"]] == [
        "image_20261003T130000",
        "image_20261003T120000",
    ]
    assert [t["take_id"] for t in listed["speeches"]] == ["speech_20261003T120000"]
    assert all("/takes/" in t["url"] for t in listed["images"] + listed["speeches"])

    select_current_take(scene, "image_20261003T120000", "image")
    assert (scene / "image.png").read_bytes() == b"old"
    cfg = yaml.safe_load((scene / "scene.yaml").read_text(encoding="utf-8"))
    assert cfg["current"]["image_take"] == "image_20261003T120000"

    select_current_take(scene, "speech_20261003T120000", "speech")
    assert (scene / "speech.wav").read_bytes() == b"wav-a"
    cfg = yaml.safe_load((scene / "scene.yaml").read_text(encoding="utf-8"))
    assert cfg["current"]["speech_take"] == "speech_20261003T120000"

    listed = list_scene_takes(scene, job_id="job", scene_id="001_shot_1")
    assert listed["images"][1]["is_current"] is True
    assert listed["speeches"][0]["is_current"] is True


def test_apply_scene_cut_keeps_takes_and_drops_extra(tmp_path: Path):
    scenes_dir = tmp_path / "scenes"
    old = scenes_dir / "001_shot_1"
    extra = scenes_dir / "002_shot_2"
    old.mkdir(parents=True)
    extra.mkdir()
    (old / "takes").mkdir()
    (old / "takes" / "image_20261003T120000.png").write_bytes(b"keep")
    (old / "image.png").write_bytes(b"keep")
    (old / "scene.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "舊標題",
                "narration": "舊口白",
                "image_prompt": "old prompt",
                "current": {"image_take": "image_20261003T120000", "speech_take": None},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (extra / "scene.yaml").write_text("id: 002_shot_2\n", encoding="utf-8")

    result = apply_scene_cut(
        tmp_path,
        [
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "新開場",
                "narration": "新的口白",
                "image_prompt": "new prompt",
            }
        ],
    )
    assert result["written"] == 1
    assert result["removed"] == 1
    assert not extra.exists()
    assert (old / "takes" / "image_20261003T120000.png").read_bytes() == b"keep"
    assert (old / "image.png").read_bytes() == b"keep"
    cfg = yaml.safe_load((old / "scene.yaml").read_text(encoding="utf-8"))
    assert cfg["narration"] == "新的口白"
    assert cfg["title"] == "新開場"
    assert cfg["current"]["image_take"] == "image_20261003T120000"


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


def test_system_status_has_gemini_and_comfy_lights():
    fields = SystemStatusResponse.model_fields
    assert "gemini_configured" in fields
    assert "comfyui_online" in fields
    assert "takes" in SceneDetail.model_fields


def test_frontend_p1_contracts():
    ts = (REPO_ROOT / "web" / "src" / "studioActions.ts").read_text(encoding="utf-8")
    assert 'scriptWorkspaceMode' in ts
    assert 'STORYBOARD_GHOST_ACTIONS' in ts
    assert "DEFAULT_USE_PIP" in ts
    editor = (REPO_ROOT / "web" / "src" / "components" / "ScriptEditor.tsx").read_text(encoding="utf-8")
    assert "美國太空總署羅曼太空望遠鏡" not in editor
    assert "故事要求" in editor
    rail = (REPO_ROOT / "web" / "src" / "components" / "SidebarRail.tsx").read_text(encoding="utf-8")
    assert "AI_TEXT_MODELS" not in rail
    assert "AI_IMAGE_MODELS" not in rail
    assert "selectJob" not in rail
    grid = (REPO_ROOT / "web" / "src" / "components" / "StoryboardGrid.tsx").read_text(encoding="utf-8")
    assert "清空圖片" not in grid
    assert "考據 (PiP)" not in grid
    assert "視覺一致性" not in grid or "尚未定裝" in grid
