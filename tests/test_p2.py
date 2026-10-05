from __future__ import annotations

from pathlib import Path

import yaml

from aivideo.acts import apply_acts_to_scenes, assign_acts, parse_outline_acts
from aivideo.job_files import FAT_JOB_KEYS, JOB_YAML_KEYS, load_job_config, save_job_config, slim_job_yaml
from aivideo.media import media_mounts, media_url_allowed, spa_dist_dir
from aivideo.run_state import load_run_json, write_run_json
from aivideo.spoken import prepare_subtitle_text
from aivideo.story_generator import create_job_bundle
from aivideo.style_prompt import compose_styled_prompt

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_slim_job_yaml_drops_fat_keys():
    slim = slim_job_yaml(
        {
            "id": "20261004_demo",
            "title": "測試",
            "voice_id": "tw_female01",
            "use_pip": False,
            "outline": "不該在 yaml",
            "custom_prompt": "也不該",
            "visual_anchors": {"subject": "x"},
            "youtube": {"video_id": "abc"},
            "kenburns": "slow_zoom_in",
        }
    )
    assert "outline" not in slim
    assert "custom_prompt" not in slim
    assert "visual_anchors" not in slim
    assert "youtube" not in slim
    assert slim["title"] == "測試"
    assert "outline" in FAT_JOB_KEYS
    assert "title" in JOB_YAML_KEYS


def test_create_job_writes_outline_and_anchors_not_yaml(tmp_path: Path, monkeypatch):
    import aivideo.story_generator as sg

    monkeypatch.setattr(sg, "REPO_ROOT", tmp_path)
    job_dir = create_job_bundle(
        job_id="20261004_p2",
        title="測試",
        scenes=[
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "開場",
                "narration": "你敢相信這件事",
                "image_prompt": "wide shot",
                "act_index": 1,
                "act_title": "開場鉤子",
            }
        ],
        outline="### 第一幕：開場鉤子\n\n衝突",
        custom_prompt="必寫看點",
        subject_anchor="a person",
        environment_anchor="rainy street",
    )
    cfg = yaml.safe_load((job_dir / "job.yaml").read_text(encoding="utf-8"))
    for key in FAT_JOB_KEYS:
        assert key not in cfg
    assert (job_dir / "outline.md").is_file()
    text = (job_dir / "outline.md").read_text(encoding="utf-8")
    assert "必寫看點" in text
    assert "第一幕" in text
    assert (job_dir / "anchors.yaml").is_file()
    anchors = yaml.safe_load((job_dir / "anchors.yaml").read_text(encoding="utf-8"))
    assert anchors["environment"] == "rainy street"
    loaded = load_job_config(job_dir)
    assert "第一幕" in loaded["outline"]
    assert loaded["custom_prompt"] == "必寫看點"
    assert loaded["visual_anchors"]["environment"] == "rainy street"


def test_save_job_config_roundtrip(tmp_path: Path):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    save_job_config(
        job_dir,
        {
            "id": "j",
            "title": "題",
            "voice_id": "tw_female01",
            "outline": "大綱正文",
            "custom_prompt": "要求",
            "visual_anchors": {"subject": "主角", "environment": "夜", "use_image_reference": True},
        },
    )
    disk = yaml.safe_load((job_dir / "job.yaml").read_text(encoding="utf-8"))
    assert "outline" not in disk
    loaded = load_job_config(job_dir)
    assert loaded["outline"] == "大綱正文"
    assert loaded["visual_anchors"]["subject"] == "主角"


def test_parse_outline_acts_and_assign():
    text = """
### 第一幕：誰是世界第六大海軍？
正文一比較長比較長比較長比較長
### 第二幕：鐵幕下的甜蜜誘惑
短
"""
    acts = parse_outline_acts(text)
    assert len(acts) == 2
    assert acts[0]["index"] == 1
    assert "第六大海軍" in acts[0]["title"]
    assigned = assign_acts(8, acts)
    assert len(assigned) == 8
    assert assigned[0]["index"] == 1
    assert assigned[-1]["index"] == 2
    scenes = [{"narration": f"n{i}"} for i in range(8)]
    apply_acts_to_scenes(scenes, acts)
    assert scenes[0]["act_title"]


def test_style_prefix_not_doubled():
    prefix = "歐式古典童話繪本插畫，溫暖水彩厚塗"
    body = f"{prefix}，a girl in a kitchen"
    assert compose_styled_prompt(prefix, body) == body
    assert compose_styled_prompt(prefix, "a girl in a kitchen").startswith(prefix)
    assert compose_styled_prompt("", "hello") == "hello"


def test_subtitle_strips_omnivoice_tags():
    assert "[surprise-wa]" not in prepare_subtitle_text("企業[surprise-wa]來了")
    assert "企業" in prepare_subtitle_text("企業[surprise-wa]來了")


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


def test_frontend_p2_contracts():
    app = (REPO_ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "patchSceneCard" in app
    assert "檢測 Gemini" in app
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
    assert 'StaticFiles(directory=str(REPO_ROOT))' not in app_py
