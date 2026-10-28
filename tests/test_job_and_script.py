"""專案設定 (job.yaml / outline.md / anchors.yaml)、腳本大綱、分鏡切鏡與畫風管理測試。"""

from __future__ import annotations

from pathlib import Path

import yaml

from aivideo.acts import apply_acts_to_scenes, assign_acts, parse_outline_acts
from aivideo.api.schemas import CreateJobRequest, GenerateOutlineRequest, UpdateJobRequest
from aivideo.job_files import (
    FAT_JOB_KEYS,
    JOB_YAML_KEYS,
    load_job_config,
    save_job_config,
    slim_job_yaml,
)
from aivideo.scene_cut import apply_scene_cut
from aivideo.story_generator import build_outline_target_spec, create_job_bundle
from aivideo.style_prompt import compose_styled_prompt


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
        job_id="20261004_job_files",
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


def test_new_job_bundle_writes_use_pip_true(tmp_path: Path, monkeypatch):
    import aivideo.story_generator as sg

    monkeypatch.setattr(sg, "REPO_ROOT", tmp_path)
    job_dir = create_job_bundle(
        job_id="20261004_pip_default",
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
    assert cfg["use_pip"] is True


def test_create_job_bundle_writes_pure_script_and_visual_pacing(tmp_path: Path, monkeypatch):
    import aivideo.story_generator as sg

    monkeypatch.setattr(sg, "REPO_ROOT", tmp_path)
    job_dir = create_job_bundle(
        job_id="20261024_pacing",
        title="節奏與純口白測試",
        scenes=[
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "第一句",
                "narration": "第一句測試口白，",
                "image_prompt": "wide shot of city",
            },
            {
                "id": "002_shot_2",
                "index": 2,
                "title": "第二句",
                "narration": "第二句測試口白，",
                "image_prompt": "close up of clock",
            },
        ],
        script_text="第一句測試口白，\n第二句測試口白，",
        visual_pacing="slow",
    )
    script_content = (job_dir / "script.md").read_text(encoding="utf-8")
    assert "畫面：" not in script_content
    assert "旁白：" not in script_content
    assert "第一句測試口白" in script_content

    cfg = yaml.safe_load((job_dir / "job.yaml").read_text(encoding="utf-8"))
    assert cfg["visual_pacing"] == "slow"


def test_default_style_and_burn_subtitles_persistence(tmp_path: Path, monkeypatch):
    from aivideo.api.routes import jobs as jobs_route
    import aivideo.story_generator as sg

    assert CreateJobRequest.model_fields["style_id"].default == "otomo_katsuhiro"

    monkeypatch.setattr(sg, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(jobs_route, "JOBS_DIR", tmp_path / "jobs")

    job_dir = sg.create_job_bundle(
        job_id="20261024_sub",
        title="字幕持久化測試",
        scenes=[
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "開場",
                "narration": "第一句測試，",
                "image_prompt": "wide shot",
            }
        ],
    )
    summary0 = jobs_route._to_job_summary(job_dir)
    assert summary0.burn_subtitles is False

    summary1 = jobs_route.update_job("20261024_sub", UpdateJobRequest(burn_subtitles=True))
    assert summary1.burn_subtitles is True
    cfg = yaml.safe_load((job_dir / "job.yaml").read_text(encoding="utf-8"))
    assert cfg["subtitle"]["mode"] == "hard"

    summary2 = jobs_route.update_job("20261024_sub", UpdateJobRequest(burn_subtitles=False))
    assert summary2.burn_subtitles is False
    cfg2 = yaml.safe_load((job_dir / "job.yaml").read_text(encoding="utf-8"))
    assert cfg2["subtitle"]["mode"] == "none"


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


def test_generate_outline_accepts_word_count():
    req = GenerateOutlineRequest(topic="測試主題", word_count=880)
    assert req.word_count == 880

    short_spec = build_outline_target_spec(880)
    assert "880" in short_spec
    assert "4000" not in short_spec

    long_spec = build_outline_target_spec(4000)
    assert "4000" in long_spec


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


def test_apply_scene_cut_clear_existing_removes_old_media_and_compose(tmp_path: Path):
    scenes_dir = tmp_path / "scenes"
    old = scenes_dir / "001_shot_1"
    old.mkdir(parents=True)
    (old / "image.png").write_bytes(b"old-img")
    (old / "speech.wav").write_bytes(b"old-wav")
    (old / "pip.png").write_bytes(b"old-pip")
    compose_dir = tmp_path / "compose"
    compose_dir.mkdir(parents=True)
    (compose_dir / "film.mp4").write_bytes(b"old-film")

    res = apply_scene_cut(
        tmp_path,
        [
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "全新第一幕",
                "narration": "全新口白，",
                "image_prompt": "brand new prompt",
                "pip_query": "Apollo 11",
            }
        ],
        clear_existing=True,
    )
    assert res["written"] == 1
    assert res["removed"] == 1
    assert not (old / "image.png").exists()
    assert not (old / "speech.wav").exists()
    assert not (old / "pip.png").exists()
    assert not compose_dir.exists()
    cfg = yaml.safe_load((old / "scene.yaml").read_text(encoding="utf-8"))
    assert cfg["narration"] == "全新口白，"
    assert cfg["pip"]["enabled"] is True
    assert cfg["pip"]["query"] == "Apollo 11"


def test_style_prefix_not_doubled():
    prefix = "歐式古典童話繪本插畫，溫暖水彩厚塗"
    body = f"{prefix}，a girl in a kitchen"
    assert compose_styled_prompt(prefix, body) == body
    assert compose_styled_prompt(prefix, "a girl in a kitchen").startswith(prefix)
    assert compose_styled_prompt("", "hello") == "hello"


def test_style_presets_extracted_to_style_prompt_module():
    import aivideo.story_generator as sg
    import aivideo.style_prompt as sp

    for attr in (
        "DEFAULT_STYLE_PRESETS",
        "load_style_presets",
        "save_all_style_presets",
        "save_style_preset",
        "delete_style_preset",
        "resolve_style",
        "style_lock_instructions",
    ):
        assert hasattr(sp, attr)
        assert getattr(sg, attr) is getattr(sp, attr)

    styles_yaml = yaml.safe_load((sp.STYLES_FILE).read_text(encoding="utf-8"))
    for key in sp.DEFAULT_STYLE_PRESETS:
        assert key in styles_yaml


def test_removed_unused_fields_and_slimmed_job_yaml(tmp_path: Path, monkeypatch):
    from aivideo.api.schemas import (
        CreateJobRequest,
        GenerateScriptRequest,
        JobSummary,
        RecutJobRequest,
        UpdateJobRequest,
    )
    from aivideo.gemini_image import MODEL_CANDIDATES
    from aivideo.naming import DEFAULT_IMAGE_MODEL
    import aivideo.story_generator as sg

    assert "metaphor_style" not in CreateJobRequest.model_fields
    assert "lines_per_scene" not in CreateJobRequest.model_fields
    assert "metaphor_style" not in UpdateJobRequest.model_fields
    assert "metaphor_style" not in RecutJobRequest.model_fields
    assert "lines_per_scene" not in RecutJobRequest.model_fields
    assert "metaphor_style" not in JobSummary.model_fields

    req = GenerateScriptRequest(topic="測試", outline="第一幕大綱")
    assert req.outline == "第一幕大綱"

    assert MODEL_CANDIDATES[0] == DEFAULT_IMAGE_MODEL == "gemini-3.1-flash-image"

    monkeypatch.setattr(sg, "REPO_ROOT", tmp_path)
    job_dir = sg.create_job_bundle(
        job_id="20261026_slim",
        title="精簡測試",
        scenes=[
            {
                "id": "001_shot_1",
                "index": 1,
                "title": "開場",
                "narration": "測試口白，",
                "image_prompt": "wide shot",
            }
        ],
    )
    cfg = yaml.safe_load((job_dir / "job.yaml").read_text(encoding="utf-8"))
    assert "style_prefix" not in cfg
    assert "style_negative" not in cfg
    assert "metaphor_style" not in cfg
    assert "model_final" not in cfg.get("image", {})
    assert cfg["image"]["model"] == DEFAULT_IMAGE_MODEL


def test_anchors_routes_extracted_and_mounted_on_jobs_router():
    from aivideo.api.app import app
    from aivideo.api.routes import anchors as anchors_route
    from aivideo.api.routes import jobs as jobs_route

    anchor_paths = {getattr(r, "path", "") for r in anchors_route.router.routes}
    assert "/jobs/analyze-anchors" in anchor_paths
    assert "/jobs/{job_id}/anchors" in anchor_paths
    assert "/jobs/{job_id}/anchors/hero" in anchor_paths
    assert "/jobs/{job_id}/anchors/characters" in anchor_paths
    assert "/jobs/{job_id}/anchors/sync-prompts" in anchor_paths

    openapi_paths = set(app.openapi().get("paths", {}).keys())
    assert "/api/v1/jobs/analyze-anchors" in openapi_paths
    assert "/jobs/{job_id}/anchors" in anchor_paths
    assert hasattr(anchors_route, "get_job_anchors")
    assert hasattr(jobs_route, "get_job_anchors")


def test_batch_generate_scene_visual_plans_chunks_and_handles_dict_wrapper(monkeypatch):
    import aivideo.story_generator as sg
    from aivideo.style_prompt import is_generic_fallback_prompt

    assert is_generic_fallback_prompt("Q版 2D 卡通插畫 cinematic wide angle shot, dramatic lighting, 16:9 widescreen composition")
    assert is_generic_fallback_prompt("cinematic wide angle shot, dramatic lighting, 16:9 widescreen composition")
    assert not is_generic_fallback_prompt(
        "Wide establishing shot of Sir Hugh Beaver aiming a double-barrel shotgun by the River Slaney in 1951 Ireland, 2D chibi cartoon illustration, 16:9 widescreen composition"
    )

    calls: list[int] = []

    def fake_chunk_call(batch_narrations, **kwargs):
        calls.append(len(batch_narrations))
        return [
            {
                "image_prompt": f"2D chibi illustration of scene {i + 1}: {txt[:10]}, 16:9 widescreen composition",
                "character_ids": ["sir_hugh_beaver"],
            }
            for i, txt in enumerate(batch_narrations)
        ]

    monkeypatch.setattr(sg, "_generate_visual_plans_chunk", fake_chunk_call)
    narrs = [f"第 {i} 幕測試口白，" for i in range(1, 26)]
    plans = sg.batch_generate_scene_visual_plans(
        narrs,
        characters=[{"id": "sir_hugh_beaver", "name": "Sir Hugh Beaver", "appearance": "Chibi gentleman"}],
        style_key="2d_chibi_cell",
    )
    assert len(plans) == 25
    assert calls == [10, 10, 5]
    assert all(not is_generic_fallback_prompt(str(p["image_prompt"])) for p in plans)
    assert plans[0]["character_ids"] == ["sir_hugh_beaver"]


def test_story_generator_does_not_force_canned_subscription_cta():
    sg_text = (Path(__file__).resolve().parents[1] / "aivideo" / "story_generator.py").read_text(encoding="utf-8")
    assert "片尾自然收尾與頻道訂閱引導（必須包含）" not in sg_text
    assert "別忘了點個喜歡，訂閱頻道，我們下一期故事" not in sg_text
    assert "嚴禁罐頭推銷" in sg_text




