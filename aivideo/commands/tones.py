from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aivideo.story_generator import extract_and_create_tone_preset

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_tones(args: argparse.Namespace) -> int:
    tones_dir = REPO_ROOT / "assets" / "tones"
    tones_dir.mkdir(parents=True, exist_ok=True)

    # 1. 若有傳入匯入檔案或文字
    import_file = getattr(args, "import_file", None)
    raw_text = getattr(args, "text", None)
    tone_id = getattr(args, "id", None)
    model = getattr(args, "model", None)

    if import_file or raw_text:
        text_content = ""
        if import_file:
            p = Path(import_file)
            if not p.is_file():
                # 嘗試相對 workspace 路徑
                p = REPO_ROOT / import_file
            if not p.is_file():
                print(f"[fail] 找不到指定的輸入文字檔：{import_file}", file=sys.stderr)
                return 1
            print(f"[tones] 正在讀取參考檔案：{p} ...")
            text_content = p.read_text(encoding="utf-8")
        elif raw_text:
            text_content = raw_text

        text_content = text_content.strip()
        if not text_content:
            print("[fail] 輸入文本內容為空。", file=sys.stderr)
            return 1

        chosen_model = model or "gemini-3.8-flash"
        print(f"[tones] ⚡ 正在呼叫 Google Cloud Vertex AI ({chosen_model}) 深度分析口白風格並萃取規範...")
        try:
            result = extract_and_create_tone_preset(
                text=text_content,
                custom_tone_id=tone_id,
                auto_save=True,
                model=model,
            )
            print("=" * 70)
            print("✨ Vertex AI Gemini Flash 已成功直接寫入專案！")
            print("=" * 70)
            print(f"  * 口吻英文識別 ID  : {result['id']}")
            print(f"  * 口吻中文名稱     : {result['title']}")
            print(f"  * 標籤分類         : {', '.join(result['tags'])}")
            print(f"  * 建議發音人指示   : {result['recommended_voice_instruct']}")
            print(f"  * 簡要描述與特徵   : {result['summary']}")
            print(f"  * 寫入檔案路徑     : {result['file_path']}")
            print("=" * 70)
            return 0
        except Exception as e:
            print(f"[fail] 萃取與寫入失敗：{e}", file=sys.stderr)
            return 1

    # 2. 預設行為：列出所有口吻範本
    print("=" * 70)
    print("🎭 AIVideo 說書人口吻風格範本清單 (Assets Tones)")
    print("=" * 70)
    md_files = sorted(tones_dir.glob("*.md"))
    valid_count = 0
    for f in md_files:
        if f.name.upper() == "README.MD":
            continue
        valid_count += 1
        lines = f.read_text(encoding="utf-8").splitlines()
        name = f.stem
        for l in lines:
            if l.startswith("name:"):
                name = l.replace("name:", "").strip().strip("\"'")
                break
        print(f"  • [{f.stem}] {name}  -->  {f.relative_to(REPO_ROOT)}")

    if valid_count == 0:
        print("  (目前尚無口吻範本)")
    print("=" * 70)
    print("💡 提示：使用 aivideo tones --import-file <路徑> 可直接由 Vertex AI Gemini Flash 萃取寫入。")
    return 0
