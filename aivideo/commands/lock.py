from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aivideo.locks import resolve_scene_dir, set_locks
from aivideo.takes import gc_job_takes, select_current_take

REPO_ROOT = Path(__file__).resolve().parents[2]


def _job_dir(args: argparse.Namespace) -> Path:
    job_dir = Path(args.job)
    if not job_dir.is_absolute():
        job_dir = REPO_ROOT / job_dir
    if not job_dir.is_dir():
        raise FileNotFoundError(f"找不到 Job：{job_dir}")
    return job_dir


def run_lock(args: argparse.Namespace) -> int:
    try:
        job_dir = _job_dir(args)
        scene_dir = resolve_scene_dir(job_dir, args.scene)
        if args.image or args.speech:
            locks = set_locks(
                scene_dir,
                image=True if args.image else None,
                speech=True if args.speech else None,
            )
        else:
            locks = set_locks(scene_dir, image=True, speech=True)
        print(f"[ok]   {scene_dir.name} locked image={locks['image']} speech={locks['speech']}")
        return 0
    except Exception as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1


def run_unlock(args: argparse.Namespace) -> int:
    try:
        job_dir = _job_dir(args)
        scene_dir = resolve_scene_dir(job_dir, args.scene)
        if args.image or args.speech:
            locks = set_locks(
                scene_dir,
                image=False if args.image else None,
                speech=False if args.speech else None,
            )
        else:
            locks = set_locks(scene_dir, image=False, speech=False)
        print(f"[ok]   {scene_dir.name} unlocked image={locks['image']} speech={locks['speech']}")
        return 0
    except Exception as extra:
        print(f"[fail] {extra}", file=sys.stderr)
        return 1


def run_select(args: argparse.Namespace) -> int:
    try:
        job_dir = _job_dir(args)
        scene_dir = resolve_scene_dir(job_dir, args.scene)
        kind = args.kind or ("image" if str(args.take).startswith("image_") else "speech")
        result = select_current_take(scene_dir, args.take, kind)
        print(f"[ok]   current {result['kind']} = {result['take_id']}")
        return 0
    except Exception as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1


def run_gc(args: argparse.Namespace) -> int:
    try:
        job_dir = _job_dir(args)
        result = gc_job_takes(job_dir, keep=args.keep, scene=getattr(args, "scene", None))
        print(f"[ok]   gc takes keep={result['keep']} scenes={result['scenes']} removed={result['removed']}")
        return 0
    except Exception as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1
