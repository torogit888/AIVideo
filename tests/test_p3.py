from __future__ import annotations

from pathlib import Path

import yaml

from aivideo.cli import build_parser
from aivideo.fonts import ASS_FONT_NAME, resolve_subtitle_font, subtitle_font_for_job
from aivideo.locks import read_locks, set_locks
from aivideo.media import spa_dist_dir
from aivideo.takes import gc_scene_takes, list_scene_takes, select_current_take

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_select_cli_helper_still_copies_current(tmp_path: Path):
    scene = _scene_with_takes(tmp_path)
    select_current_take(scene, "image_20261001T120000", "image")
    assert (scene / "image.png").read_bytes() == b"old"


def test_cli_has_lock_unlock_select_gc():
    parser = build_parser()
    names = []
    for action in parser._subparsers._actions:
        if getattr(action, "choices", None):
            names.extend(action.choices.keys())
    assert "lock" in names
    assert "unlock" in names
    assert "select" in names
    assert "gc" in names
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


def test_spa_dist_helper():
    assert spa_dist_dir(REPO_ROOT) is None or (REPO_ROOT / "web" / "dist" / "index.html").is_file()
    app_py = (REPO_ROOT / "aivideo" / "api" / "app.py").read_text(encoding="utf-8")
    assert "spa_dist_dir" in app_py


def test_frontend_p3_contracts():
    inspector = (REPO_ROOT / "web" / "src" / "components" / "SceneInspector.tsx").read_text(encoding="utf-8")
    assert "handleToggleLock" in inspector
    assert "gcSceneTakes" in inspector
    assert "畫面已鎖" in inspector
    app = (REPO_ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "檢測 Gemini" in app
    assert "預設發音人" in app
    settings = app
    assert "font_ok" in settings
