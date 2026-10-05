"""分鏡 image／speech lock。鎖定後批次與重抽預設跳過。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

LOCK_KINDS = ("image", "speech")


def _load(scene_dir: Path) -> dict[str, Any]:
    path = scene_dir / "scene.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"找不到 scene.yaml：{path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _save(scene_dir: Path, data: dict[str, Any]) -> None:
    (scene_dir / "scene.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def read_locks(scene_dir: Path) -> dict[str, bool]:
    data = _load(scene_dir)
    locks = data.get("locks") if isinstance(data.get("locks"), dict) else {}
    return {
        "image": bool(locks.get("image", False)),
        "speech": bool(locks.get("speech", False)),
    }


def set_locks(scene_dir: Path, image: bool | None = None, speech: bool | None = None) -> dict[str, bool]:
    data = _load(scene_dir)
    locks = data.get("locks") if isinstance(data.get("locks"), dict) else {}
    if image is not None:
        locks["image"] = bool(image)
    if speech is not None:
        locks["speech"] = bool(speech)
    locks.setdefault("image", False)
    locks.setdefault("speech", False)
    data["locks"] = locks
    _save(scene_dir, data)
    return {"image": bool(locks["image"]), "speech": bool(locks["speech"])}


def resolve_scene_dir(job_dir: Path, scene: str) -> Path:
    scenes = job_dir / "scenes"
    if not scenes.is_dir():
        raise FileNotFoundError(f"找不到 scenes：{scenes}")
    exact = scenes / scene
    if exact.is_dir():
        return exact
    matches = [
        p
        for p in sorted(scenes.iterdir())
        if p.is_dir() and (p.name == scene or p.name.startswith(f"{scene}_") or p.name.startswith(scene))
    ]
    if not matches:
        raise FileNotFoundError(f"找不到分鏡 {scene}")
    return matches[0]
