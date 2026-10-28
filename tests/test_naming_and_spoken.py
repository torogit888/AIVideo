"""命名規則、口白清洗、發音替換、SRT 字幕與時間軸解析測試。"""

from __future__ import annotations

from pathlib import Path

import yaml

from aivideo.commands.srt import generate_srt, wrap_subtitle_text
from aivideo.film_cues import parse_scene_cues
from aivideo.naming import (
    ascii_slug,
    build_job_id,
    resolve_unique_job_id,
    scene_folder_id,
    scene_title_from_narration,
    srt_media_url,
)
from aivideo.spoken import prepare_subtitle_text, prepare_tts_text


def test_ascii_slug_from_chinese_topic():
    slug = ascii_slug("百事可樂的蘇聯海軍")
    assert slug == "story"
    assert all(c.isalnum() or c in "_-" for c in slug)


def test_custom_slug_goes_into_job_id():
    job_id = build_job_id("百事可樂的蘇聯海軍", slug="pepsi_navy", today="20261003")
    assert job_id == "20261003_pepsi_navy"


def test_resolve_unique_job_id_auto_suffix(tmp_path: Path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    assert resolve_unique_job_id(jobs_dir, "20261024_story") == "20261024_story"

    (jobs_dir / "20261024_story").mkdir()
    assert resolve_unique_job_id(jobs_dir, "20261024_story") == "20261024_story_2"

    (jobs_dir / "20261024_story_2").mkdir()
    assert resolve_unique_job_id(jobs_dir, "20261024_story") == "20261024_story_3"


def test_scene_id_ascii_and_title_chinese():
    sid = scene_folder_id(1)
    assert all(c.isascii() for c in sid)
    title = scene_title_from_narration("你敢相信，一家專門賣氣泡飲料的公司[surprise-wa]")
    assert any("\u4e00" <= ch <= "\u9fff" for ch in title)
    assert title != "第 1 幕"
    assert "第" not in title or "幕" not in title


def test_srt_download_url_uses_timeline():
    url = srt_media_url("20261003_pepsi_navy")
    assert url.endswith("timeline.srt")
    assert "film.srt" not in url


def test_pronunciation_and_tags_only_for_tts():
    spoken = "一家賣氣泡飲料的企業[surprise-wa]"
    assert "企業" in spoken
    yaml_text = prepare_subtitle_text(spoken)
    assert "企業" in yaml_text
    assert "[" not in yaml_text
    tts = prepare_tts_text(spoken)
    assert "氣業" in tts
    assert "[surprise-wa]" in tts


def test_subtitle_strips_omnivoice_tags():
    assert "[surprise-wa]" not in prepare_subtitle_text("企業[surprise-wa]來了")
    assert "企業" in prepare_subtitle_text("企業[surprise-wa]來了")


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


def test_spoken_sanitization_and_cta_merge_extracted():
    import aivideo.scene_cut as sc
    import aivideo.spoken as sp
    import aivideo.story_generator as sg

    for fn_name in (
        "extract_outline_leak_phrases",
        "is_non_spoken_script_line",
        "extract_tone_spoken_sample",
        "split_long_narration_line",
        "sanitize_script_punctuation",
        "resolve_host_persona_name",
        "deidentify_and_bind_tone",
    ):
        assert hasattr(sp, fn_name)
        assert getattr(sg, fn_name) is getattr(sp, fn_name)

    for fn_name in ("is_cta_line", "merge_trailing_cta_chunks"):
        assert hasattr(sc, fn_name)
        assert getattr(sg, fn_name) is getattr(sc, fn_name)

    cleaned = sp.sanitize_script_punctuation("第一幕：開場\n旁白：你敢相信「這件事」嗎？今天我們來聊聊。")
    assert "第一幕" not in cleaned
    assert "旁白：" not in cleaned
    assert "「" not in cleaned
    assert "你敢相信這件事嗎？" in cleaned

    assert sp.resolve_host_persona_name("開頭: 大家好~我是白兔!") == "白兔"
    assert sp.resolve_host_persona_name("開頭: 無自稱（直接破題）") == ""

    merged = sc.merge_trailing_cta_chunks([["故事最後一句，"], ["別忘了點讚訂閱開啟小鈴鐺，"]])
    assert len(merged) == 1
    assert len(merged[0]) == 2

