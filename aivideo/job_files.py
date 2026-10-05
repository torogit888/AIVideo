"""Job 檔案邊界：短 job.yaml、outline.md、anchors.yaml。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

JOB_YAML_KEYS = (
    "id",
    "title",
    "language",
    "voice_id",
    "use_pip",
    "tone_id",
    "frame",
    "image",
    "style_prefix",
    "style_negative",
    "subtitle",
    "kenburns",
)

FAT_JOB_KEYS = ("outline", "custom_prompt", "visual_anchors", "youtube")

_PROMPT_HEAD = re.compile(r"^##\s*指定 Prompt[^\n]*\n+", re.M)
_OUTLINE_HEAD = re.compile(r"^##\s*(?:[0-9]+\s*幕)?故事大綱[^\n]*\n+", re.M)


def slim_job_yaml(cfg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in JOB_YAML_KEYS:
        if key in cfg and cfg[key] is not None:
            out[key] = cfg[key]
    return out


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_outline_md(job_dir: Path, title: str, outline: str = "", custom_prompt: str = "") -> None:
    lines = [f"# {title} - 故事大綱與企劃設定\n"]
    if (custom_prompt or "").strip():
        lines.append(f"## 指定 Prompt 與故事特定要求\n\n{custom_prompt.strip()}\n")
    if (outline or "").strip():
        lines.append(f"## 故事大綱\n\n{outline.strip()}\n")
    (job_dir / "outline.md").write_text("\n".join(lines), encoding="utf-8")


def read_outline_md(job_dir: Path) -> tuple[str, str]:
    """回傳 (outline 正文, custom_prompt)。沒有檔則空字串。"""
    path = job_dir / "outline.md"
    if not path.is_file():
        return "", ""
    text = path.read_text(encoding="utf-8")
    custom = ""
    outline = ""
    prompt_m = re.search(
        r"##\s*指定 Prompt[^\n]*\n+(.*?)(?=\n## |\Z)",
        text,
        re.S,
    )
    if prompt_m:
        custom = prompt_m.group(1).strip()
    outline_m = re.search(
        r"##\s*(?:[0-9]+\s*幕)?故事大綱[^\n]*\n+(.*)",
        text,
        re.S,
    )
    if outline_m:
        outline = outline_m.group(1).strip()
    elif not custom:
        outline = text.strip()
    return outline, custom


def read_outline_text(job_dir: Path) -> str:
    outline, _custom = read_outline_md(job_dir)
    if outline:
        return outline
    path = job_dir / "outline.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def write_anchors(job_dir: Path, anchors: dict[str, Any]) -> None:
    write_yaml(job_dir / "anchors.yaml", anchors or {})


def read_anchors(job_dir: Path) -> dict[str, Any] | None:
    path = job_dir / "anchors.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_job_config(job_dir: Path) -> dict[str, Any]:
    path = job_dir / "job.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"找不到 job.yaml：{path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(cfg, dict):
        cfg = {}

    outline, custom = read_outline_md(job_dir)
    if outline:
        cfg["outline"] = outline
    if custom:
        cfg["custom_prompt"] = custom

    anchors = read_anchors(job_dir)
    if anchors is not None:
        cfg["visual_anchors"] = anchors
    elif not isinstance(cfg.get("visual_anchors"), dict):
        cfg["visual_anchors"] = {}
    return cfg


def save_job_config(job_dir: Path, cfg: dict[str, Any]) -> None:
    title = str(cfg.get("title") or job_dir.name)
    outline = str(cfg.get("outline") or "")
    custom = str(cfg.get("custom_prompt") or "")
    if outline or custom or (job_dir / "outline.md").is_file():
        write_outline_md(job_dir, title, outline=outline, custom_prompt=custom)

    anchors = cfg.get("visual_anchors")
    if isinstance(anchors, dict):
        write_anchors(job_dir, anchors)
    elif (job_dir / "anchors.yaml").is_file() is False and isinstance(cfg.get("visual_anchors"), dict):
        write_anchors(job_dir, cfg["visual_anchors"])

    write_yaml(job_dir / "job.yaml", slim_job_yaml(cfg))
