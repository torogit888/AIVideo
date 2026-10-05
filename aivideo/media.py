"""縮小 /media 掛載：只暴露 jobs、風格預覽、語音試聽、字型。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def media_mounts(repo_root: Path | None = None) -> list[tuple[str, Path]]:
    root = Path(repo_root or REPO_ROOT)
    mounts = [
        ("/media/jobs", root / "jobs"),
        ("/media/assets/styles/previews", root / "assets" / "styles" / "previews"),
        ("/media/assets/voices", root / "assets" / "voices"),
        ("/media/assets/fonts", root / "assets" / "fonts"),
    ]
    return [(url, path) for url, path in mounts if path.is_dir()]


def media_url_allowed(url_path: str) -> bool:
    """給測試用：路徑是否落在允許的 /media 前綴。"""
    allowed = (
        "/media/jobs/",
        "/media/assets/styles/previews/",
        "/media/assets/voices/",
        "/media/assets/fonts/",
    )
    p = url_path if url_path.endswith("/") else url_path + "/"
    if url_path.rstrip("/") in ("/media/jobs", "/media/assets/styles/previews", "/media/assets/voices", "/media/assets/fonts"):
        return True
    return any(url_path.startswith(a) or p.startswith(a) for a in allowed)


def spa_dist_dir(repo_root: Path | None = None) -> Path | None:
    dist = Path(repo_root or REPO_ROOT) / "web" / "dist"
    if dist.is_dir() and (dist / "index.html").is_file():
        return dist
    return None
