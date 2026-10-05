from __future__ import annotations

from pathlib import Path

import yaml

from aivideo.api.schemas import CreateJobRequest, JobSummary
from aivideo.commands.srt import generate_srt, wrap_subtitle_text
from aivideo.film_cues import parse_scene_cues
from aivideo.naming import (
    DEFAULT_VOICE_ID,
    ascii_slug,
    build_job_id,
    primary_pipeline_action,
    scene_folder_id,
    scene_title_from_narration,
    should_auto_pip,
    srt_media_url,
)
from aivideo.spoken import prepare_subtitle_text, prepare_tts_text

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_all_action_does_not_auto_pip():
    assert should_auto_pip("all") is False
    assert should_auto_pip("images") is False
    assert should_auto_pip("tts") is False
    assert should_auto_pip("pip") is True


def test_primary_button_follows_missing_assets():
    assert primary_pipeline_action(0, 0, 10, False)["action"] == "images"
    assert primary_pipeline_action(0, 0, 10, False)["label"] == "生成未完成畫面"
    assert primary_pipeline_action(10, 3, 10, False)["action"] == "tts"
    assert primary_pipeline_action(10, 3, 10, False)["label"] == "生成配音"
    assert primary_pipeline_action(10, 10, 10, False)["action"] == "compose"
    assert primary_pipeline_action(10, 10, 10, True)["action"] == "preview"
    assert primary_pipeline_action(10, 10, 10, True)["label"] == "預覽成片"


def test_srt_download_url_uses_timeline():
    url = srt_media_url("20261003_pepsi_navy")
    assert url.endswith("timeline.srt")
    assert "film.srt" not in url


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
    assert "female01" not in naming


def test_ascii_slug_from_chinese_topic():
    slug = ascii_slug("百事可樂的蘇聯海軍")
    assert slug == "story"
    assert all(c.isalnum() or c in "_-" for c in slug)


def test_custom_slug_goes_into_job_id():
    job_id = build_job_id("百事可樂的蘇聯海軍", slug="pepsi_navy", today="20261003")
    assert job_id == "20261003_pepsi_navy"


def test_scene_id_ascii_and_title_chinese():
    sid = scene_folder_id(1)
    assert all(c.isascii() for c in sid)
    title = scene_title_from_narration("你敢相信，一家專門賣氣泡飲料的公司[surprise-wa]")
    assert any("\u4e00" <= ch <= "\u9fff" for ch in title)
    assert title != "第 1 幕"
    assert "第" not in title or "幕" not in title


def test_pronunciation_and_tags_only_for_tts():
    spoken = "一家賣氣泡飲料的企業[surprise-wa]"
    assert "企業" in spoken
    yaml_text = prepare_subtitle_text(spoken)
    assert "企業" in yaml_text
    assert "[" not in yaml_text
    tts = prepare_tts_text(spoken)
    assert "氣業" in tts
    assert "[surprise-wa]" in tts


def test_srt_keeps_hanzi_drops_tags(tmp_path: Path):
    scene_dir = tmp_path / "scenes" / "001_shot_1"
    scene_dir.mkdir(parents=True)
    (scene_dir / "scene.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "001_shot_1",
                "title": "氣泡企業",
                "narration": "一家賣氣泡飲料的企業[surprise-wa]",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    srt_path, _ass = generate_srt(tmp_path)
    text = srt_path.read_text(encoding="utf-8")
    assert "企業" in text
    assert "氣業" not in text
    assert "[surprise-wa]" not in text
    wrapped = wrap_subtitle_text("企業[surprise-wa]來了")
    assert all("[" not in line for line in wrapped)
    assert any("企業" in line for line in wrapped)


def test_parse_scene_cues_from_job_dir(tmp_path: Path):
    for idx, dur in ((1, 2.0), (2, 3.5)):
        s_dir = tmp_path / "scenes" / f"00{idx}_shot_{idx}"
        s_dir.mkdir(parents=True)
        (s_dir / "scene.yaml").write_text(
            yaml.safe_dump(
                {"id": f"00{idx}_shot_{idx}", "title": f"短句{idx}"},
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        (s_dir / "speech.json").write_text(
            f'{{"duration_sec": {dur}}}',
            encoding="utf-8",
        )
    cues = parse_scene_cues(tmp_path)
    assert [c["scene_id"] for c in cues] == ["001_shot_1", "002_shot_2"]
    assert cues[0]["start_sec"] == 0.0
    assert cues[0]["end_sec"] == 2.0
    assert cues[1]["start_sec"] == 2.0
    assert cues[1]["end_sec"] == 5.5


def test_streamlit_removed_and_studio_ports():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "streamlit" not in pyproject
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "8501" not in compose
    assert "8000" in compose
    assert not (REPO_ROOT / "aivideo" / "webui.py").exists()
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "5173" in readme
    assert "8000" in readme
    assert "uvicorn" in readme
