"""字幕字型：優先 assets/fonts，再退到容器裡的 Noto CJK。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ASS_FONT_NAME = "Noto Sans CJK TC"

_CANDIDATES = (
    REPO_ROOT / "assets" / "fonts" / "NotoSansTC-Regular.otf",
    REPO_ROOT / "assets" / "fonts" / "NotoSansCJKtc-Regular.otf",
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf"),
    Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto-cjk/NotoSansCJK-Regular.ttc"),
)


def resolve_subtitle_font() -> dict[str, str | None]:
    """回傳 ass 用的 Fontname 與真實檔案路徑（若找得到）。"""
    for path in _CANDIDATES:
        try:
            if path.is_file():
                return {
                    "font_name": ASS_FONT_NAME,
                    "font_path": str(path),
                    "ok": True,
                }
        except OSError:
            continue
    return {"font_name": ASS_FONT_NAME, "font_path": None, "ok": False}


def subtitle_font_for_job() -> str:
    info = resolve_subtitle_font()
    return str(info["font_path"] or info["font_name"])
