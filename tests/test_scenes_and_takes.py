"""分鏡畫面就緒判定、成片過期偵測、歷史版本 (Takes)、GC 清理與分鏡鎖定測試。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from aivideo.api.routes.jobs import _calculate_job_progress, _to_job_summary
from aivideo.api.routes.scenes import _get_scene_status
from aivideo.locks import read_locks, set_locks
from aivideo.naming import is_scene_visual_ready
from aivideo.takes import (
    gc_scene_takes,
    list_scene_takes,
    prune_scene_takes_after_adopt,
    select_current_take,
)


def _scene_with_takes(tmp_path: Path) -> Path:
    scene = tmp_path / "scenes" / "001_shot_1"
    takes = scene / "takes"
    takes.mkdir(parents=True)
    (takes / "image_20261001T120000.png").write_bytes(b"old")
    (takes / "image_20261002T120000.png").write_bytes(b"mid")
    (takes / "image_20261003T120000.png").write_bytes(b"new")
    (takes / "image_20261003T120000.json").write_text("{}", encoding="utf-8")
    (takes / "speech_20261001T120000.wav").write_bytes(b"a")
    (takes / "speech_20261002T120000.wav").write_bytes(b"b")
    (takes / "speech_20261002T120000_sent_1.wav").write_bytes(b"skip")
    (scene / "scene.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "001_shot_1",
                "locks": {"image": False, "speech": False},
                "current": {"image_take": "image_20261003T120000", "speech_take": "speech_20261002T120000"},
            }
        ),
        encoding="utf-8",
    )
    return scene


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


def test_lock_and_unlock(tmp_path: Path):
    scene = _scene_with_takes(tmp_path)
    set_locks(scene, image=True, speech=False)
    locks = read_locks(scene)
    assert locks["image"] is True
    assert locks["speech"] is False
    set_locks(scene, speech=True)
    locks = read_locks(scene)
    assert locks["speech"] is True
    set_locks(scene, image=False, speech=False)
    locks = read_locks(scene)
    assert locks["image"] is False


def test_gc_keeps_current_and_newest(tmp_path: Path):
    scene = _scene_with_takes(tmp_path)
    result = gc_scene_takes(scene, keep=2)
    assert result["removed"] >= 1
    listed = list_scene_takes(scene)
    ids = [t["take_id"] for t in listed["images"]]
    assert "image_20261003T120000" in ids
    assert "image_20261001T120000" not in ids
    assert not (scene / "takes" / "speech_20261002T120000_sent_1.wav").exists()


def test_prune_after_adopt_keeps_current_and_three_newest(tmp_path: Path):
    scene = tmp_path / "scenes" / "001_shot_1"
    takes = scene / "takes"
    takes.mkdir(parents=True)
    for day in ("20261001", "20261002", "20261003", "20261004", "20261005"):
        (takes / f"image_{day}T120000.png").write_bytes(day.encode())
        (takes / f"image_{day}T120000.json").write_text(
            json.dumps({"created_at": f"{day}T12:00:00"}),
            encoding="utf-8",
        )
        (takes / f"speech_{day}T120000.wav").write_bytes(day.encode())
        (takes / f"speech_{day}T120000.json").write_text(
            json.dumps({"created_at": f"{day}T12:00:00"}),
            encoding="utf-8",
        )
    (takes / "speech_20261005T120000_sent_1.wav").write_bytes(b"aux")
    (scene / "scene.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "001_shot_1",
                "current": {
                    "image_take": "image_20261001T120000",
                    "speech_take": "speech_20261005T120000",
                },
            }
        ),
        encoding="utf-8",
    )

    result = prune_scene_takes_after_adopt(scene)
    listed = list_scene_takes(scene)
    image_ids = [t["take_id"] for t in listed["images"]]
    speech_ids = [t["take_id"] for t in listed["speeches"]]

    assert result["removed"] >= 1
    assert image_ids == [
        "image_20261005T120000",
        "image_20261004T120000",
        "image_20261003T120000",
        "image_20261001T120000",
    ]
    assert speech_ids == [
        "speech_20261005T120000",
        "speech_20261004T120000",
        "speech_20261003T120000",
    ]
    assert (takes / "image_20261001T120000.png").read_bytes() == b"20261001"
    assert not (takes / "image_20261002T120000.png").exists()
    assert not (takes / "speech_20261001T120000.wav").exists()
    assert not (takes / "speech_20261005T120000_sent_1.wav").exists()


def test_select_cli_helper_still_copies_current(tmp_path: Path):
    scene = _scene_with_takes(tmp_path)
    select_current_take(scene, "image_20261001T120000", "image")
    assert (scene / "image.png").read_bytes() == b"old"


def test_scene_visual_ready_unified_across_overview_and_storyboard(tmp_path: Path):
    job_dir = tmp_path / "20261024_visual_check"
    scenes_dir = job_dir / "scenes"
    # Scene 1: 只有黑底 spotlight 考據照片 pip.png（無 image.png）-> 應視為畫面完成
    s1 = scenes_dir / "001_shot_1"
    s1.mkdir(parents=True)
    (s1 / "pip.png").write_bytes(b"png")
    (s1 / "scene.yaml").write_text(
        yaml.safe_dump({"id": "001_shot_1", "pip": {"enabled": True, "mode": "spotlight"}}),
        encoding="utf-8",
    )
    # Scene 2: 只有小卡 pip.png（mode: pip，無 image.png）-> 背景圖未完成，不應算畫面完成
    s2 = scenes_dir / "002_shot_2"
    s2.mkdir(parents=True)
    (s2 / "pip.png").write_bytes(b"png")
    (s2 / "scene.yaml").write_text(
        yaml.safe_dump({"id": "002_shot_2", "pip": {"enabled": True, "mode": "pip"}}),
        encoding="utf-8",
    )
    # Scene 3: 有考據影片 pip.mp4 -> 應視為畫面完成
    s3 = scenes_dir / "003_shot_3"
    s3.mkdir(parents=True)
    (s3 / "pip.mp4").write_bytes(b"mp4")
    (s3 / "scene.yaml").write_text(
        yaml.safe_dump({"id": "003_shot_3", "pip": {"enabled": True, "mode": "broll"}}),
        encoding="utf-8",
    )

    assert is_scene_visual_ready(s1) is True
    assert is_scene_visual_ready(s2) is False
    assert is_scene_visual_ready(s3) is True

    assert _get_scene_status(s1, job_dir.name).has_image is True
    assert _get_scene_status(s2, job_dir.name).has_image is False
    assert _get_scene_status(s3, job_dir.name).has_image is True

    prog = _calculate_job_progress(job_dir)
    assert prog.scenes_count == 3
    assert prog.images_ready == 2

    # 舊專案 job.yaml 沒寫 use_pip 時，_to_job_summary 應回傳 True
    (job_dir / "job.yaml").write_text(
        yaml.safe_dump({"id": job_dir.name, "title": "測試"}), encoding="utf-8"
    )
    summary = _to_job_summary(job_dir)
    assert summary.use_pip is True


def test_film_stale_detection(tmp_path: Path):
    job_dir = tmp_path / "20261024_stale_check"
    s1 = job_dir / "scenes" / "001_shot_1"
    compose_dir = job_dir / "compose"
    s1.mkdir(parents=True)
    compose_dir.mkdir(parents=True)

    script_file = job_dir / "script.md"
    scene_yaml = s1 / "scene.yaml"
    img_file = s1 / "image.png"
    wav_file = s1 / "speech.wav"
    film_file = compose_dir / "film.mp4"

    script_file.write_text("舊口白", encoding="utf-8")
    scene_yaml.write_text("id: 001_shot_1\nnarration: 舊口白\n", encoding="utf-8")
    img_file.write_bytes(b"img")
    wav_file.write_bytes(b"wav")
    film_file.write_bytes(b"mp4")

    base_ts = 1_700_000_000
    for f in (script_file, scene_yaml, img_file, wav_file):
        os.utime(f, (base_ts, base_ts))
    os.utime(film_file, (base_ts + 10, base_ts + 10))

    prog_fresh = _calculate_job_progress(job_dir)
    assert prog_fresh.film_ready is True
    assert prog_fresh.film_stale is False
    assert prog_fresh.film_mtime == base_ts + 10

    # 修改口白或重配音（時間比 film.mp4 新）-> film_stale 應為 True
    os.utime(scene_yaml, (base_ts + 20, base_ts + 20))
    prog_stale = _calculate_job_progress(job_dir)
    assert prog_stale.film_ready is True
    assert prog_stale.film_stale is True
    assert prog_stale.film_mtime == base_ts + 10
