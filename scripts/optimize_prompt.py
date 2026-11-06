"""自動化最佳化 Prompt 迭代腳本 (ComfyUI Z-Image Turbo)。

透過多模態 Vision AI 評估每輪生成圖片與目標圖片的視覺差異，
迭代微調正向與負面提示詞，並即時生成可視化 review.html 儀表板供審查。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _is_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("DOCKER_CONTAINER") == "1"


def _clean_arg(val: list[str] | str | None) -> str:
    if isinstance(val, list):
        res = " ".join(val).strip()
    elif isinstance(val, str):
        res = val.strip()
    else:
        res = ""
    if res.startswith(('"', "'")) and res.endswith(('"', "'")) and len(res) >= 2:
        res = res[1:-1].strip()
    return res


def _normalize_repo_path(raw_path: str) -> Path:
    p = Path(raw_path.strip().strip('"').strip("'"))
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p


def clamp_prompt_weights(prompt_text: str, min_weight: float = 0.7, max_weight: float = 1.3) -> str:
    """對 Prompt 中的標籤權重進行硬性夾剪 (Clamp)，防止權重失控 (>1.3) 導致潛空間過曝崩壞。"""
    if not prompt_text:
        return ""

    import re

    def _clamp_match(match: re.Match) -> str:
        tag = match.group(1).strip()
        try:
            val = float(match.group(2))
        except ValueError:
            return match.group(0)

        if val > max_weight:
            return f"({tag}:{max_weight:.1f})"
        elif val < min_weight:
            return f"({tag}:{min_weight:.1f})"
        elif 0.95 <= val <= 1.05:
            return tag
        return f"({tag}:{val:.1f})"

    # 1. 匹配標準 (content:weight)
    clamped = re.sub(r"\(([^:()]+):([0-9]*\.?[0-9]+)\)", _clamp_match, prompt_text)

    # 2. 清理多餘的層層括號 (((tag))) -> (tag:1.2), ((tag)) -> (tag:1.1)
    clamped = re.sub(r"\(\(\(([^()]+)\)\)\)", r"(\1:1.2)", clamped)
    clamped = re.sub(r"\(\(([^()]+)\)\)", r"(\1:1.1)", clamped)
    return clamped


# ==============================================================================
# 容器內部核心邏輯 (Docker Pipeline Runner)
# ==============================================================================

def _calculate_pixel_similarity(target_path: Path, current_path: Path) -> float:
    """備用：以圖像顏色與特徵直方圖相關性計算粗略視覺相似度 (0~100)"""
    try:
        from PIL import Image
        import numpy as np

        img1 = Image.open(target_path).convert("RGB").resize((256, 256))
        img2 = Image.open(current_path).convert("RGB").resize((256, 256))
        arr1 = np.asarray(img1, dtype=np.float32)
        arr2 = np.asarray(img2, dtype=np.float32)

        # 結合 MSE 與直方圖相關性
        mse = np.mean((arr1 - arr2) ** 2)
        psnr = 20 * np.log10(255.0 / (np.sqrt(mse) + 1e-6))
        # 將 PSNR (15~40dB) 映射至約 50~99%
        score = np.clip((psnr - 15) / 25.0 * 50 + 50, 40.0, 98.0)
        return float(round(score, 1))
    except Exception:
        return 70.0


def _evaluate_with_gemini_vision(
    target_img_bytes: bytes,
    current_img_bytes: bytes,
    current_prompt: str,
    current_negative: str,
    rollback_info: str = "",
) -> dict[str, Any]:
    """使用 Gemini Vision 多模態分析評估兩張圖片之視覺相似度與細部差異，並產出下一輪 Prompt 修正建議。"""
    from aivideo.commands.check import _load_dotenv
    _load_dotenv()
    from aivideo.gemini_image import get_gemini_client_kwargs
    from google import genai
    from google.genai import types

    system_instruction = (
        "You are an expert AI Concept Artist and Prompt Engineer specializing in diffusion models "
        "(SDXL, Z-Image Turbo, and 2D chibi cel art styles). "
        "Your task is to compare a TARGET reference image with a CURRENT model-generated image, "
        "evaluate visual similarity accurately on a 0-100 scale, and formulate actionable prompt refinements "
        "to steer the next generation closer to the target."
    )

    rollback_section = ""
    if rollback_info:
        rollback_section = f"""
================================================================================
⚠️ ROLLBACK ALERT FROM PREVIOUS ITERATION:
{rollback_info}
================================================================================
"""

    eval_prompt = f"""Compare the two attached images:
- Image 1 is the TARGET reference character illustration.
- Image 2 is the CURRENT generated image from our image model.

The current prompts used were:
- Positive Prompt: {current_prompt}
- Negative Prompt: {current_negative}
{rollback_section}
Perform a rigorous visual comparison across:
1. Art style (line art thickness, cel-shading, color palette, lighting mood).
2. Face & head (eyes, mustache/beard style, facial proportions, hairline, hair color).
3. Body & pose (chibi proportions, build, stature, posture).
4. Signature attire (suit jacket, lapels, collar, tie, buttons, fabric tones).
5. Background & framing (neutral minimalist background, clean composition).

CRITICAL PROMPT REFINEMENT RULES:
1. STRICT WEIGHT LIMIT: NEVER use weight multipliers above 1.3 or below 0.7 (e.g. max `(tag:1.3)`). Weights > 1.3 cause severe image degradation, artifacts, and duplicate characters in diffusion models.
2. SUBTLE INCREMENTAL CHANGES: Change or add at most 1-3 targeted attributes per round. Do NOT rewrite the whole prompt or add dozens of tags.
3. PREFER DESCRIPTIONS OVER WEIGHTS: Use concise natural adjectives (e.g. "small thin mustache with trimmed ends", "single gentleman on plain solid light grey background") rather than stacking high weights.

Output a valid JSON object strictly matching this schema:
{{
  "similarity_score": <int between 0 and 100 representing visual closeness>,
  "critique": "Brief 2-3 sentence analysis of differences and why this score was given.",
  "positive_prompt": "Refined and optimized English positive prompt for the next iteration to fix missing or inaccurate features.",
  "negative_prompt": "Refined negative prompt to suppress artifacts, incorrect body parts, or style drifts.",
  "key_adjustments": ["Bullet point 1 of concrete change made", "Bullet point 2"]
}}
"""

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-3.1-flash",
        "gemini-2.0-flash",
    ]

    for model_name in models_to_try:
        try:
            client = genai.Client(**get_gemini_client_kwargs(model=model_name))
            contents = [
                types.Part.from_bytes(data=target_img_bytes, mime_type="image/png"),
                types.Part.from_bytes(data=current_img_bytes, mime_type="image/png"),
                eval_prompt,
            ]
            resp = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
            if resp.text:
                data = json.loads(resp.text)
                if "similarity_score" in data:
                    return data
        except Exception as exc:
            print(f"[warn] Gemini Vision 模型 {model_name} 評估重試中: {exc}", file=sys.stderr)
            continue

    return {
        "similarity_score": 75,
        "critique": "無法連線至 Gemini Vision API 進行語意分析，使用預設修正策略。",
        "positive_prompt": current_prompt,
        "negative_prompt": current_negative,
        "key_adjustments": ["維持目前提示詞並調試生成"],
    }


def _render_review_html(
    run_dir: Path,
    target_img_name: str,
    history: list[dict[str, Any]],
    target_score: int,
) -> Path:
    """產出獨立且美觀的 HTML 互動審查報告。"""
    html_path = run_dir / "review.html"

    cards_html = []
    for item in history:
        iter_num = item["iteration"]
        score = item["similarity_score"]
        img_file = item["image"]
        pos_p = item["prompt"]
        neg_p = item["negative_prompt"]
        critique = item["critique"]
        adjustments = "".join(f"<li>{adj}</li>" for adj in item.get("key_adjustments", []))

        badge_class = "score-high" if score >= 90 else ("score-mid" if score >= 75 else "score-low")
        badges = [f'<span class="score-badge {badge_class}">{score}% 相似度</span>']
        if item.get("rollback"):
            badges.append('<span class="score-badge score-rollback">⚠️ 已回退 (Rolled Back)</span>')
        if item.get("is_best"):
            badges.append('<span class="score-badge score-best">🏆 歷史最佳</span>')
        badges_html = " ".join(badges)

        cards_html.append(f"""
        <div class="iteration-card">
          <div class="iter-header">
            <span class="iter-title">Iteration #{iter_num:02d}</span>
            <div>{badges_html}</div>
          </div>
          <div class="iter-body">
            <div class="iter-media">
              <img src="{img_file}" alt="Iteration {iter_num}" onclick="window.open('{img_file}')" title="點擊檢視原圖">
            </div>
            <div class="iter-details">
              <div class="critique-box">
                <strong>視覺差異分析與評語：</strong>
                <p>{critique}</p>
                {f'<ul class="adj-list">{adjustments}</ul>' if adjustments else ''}
              </div>
              <div class="prompt-box">
                <div class="prompt-label">正面提示詞 (Positive Prompt):</div>
                <pre class="prompt-text">{pos_p}</pre>
                <div class="prompt-label">負面提示詞 (Negative Prompt):</div>
                <pre class="prompt-text">{neg_p}</pre>
              </div>
            </div>
          </div>
        </div>
        """)

    best_item = max(history, key=lambda x: x["similarity_score"]) if history else None
    best_score = best_item["similarity_score"] if best_item else 0
    best_prompt = best_item["prompt"] if best_item else ""
    best_image = best_item["image"] if best_item else target_img_name

    full_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AIVideo: Prompt 最佳化迭代報告</title>
  <style>
    :root {{
      --bg: #0f141c;
      --card-bg: #1a2230;
      --accent: #3b82f6;
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-red: #ef4444;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --border: #2e384d;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text-main);
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    header {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px 24px;
      margin-bottom: 24px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }}
    h1 {{ font-size: 1.5rem; font-weight: 700; color: #60a5fa; }}
    .meta-pills {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .pill {{
      background: rgba(255,255,255,0.06);
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 0.875rem;
      border: 1px solid var(--border);
    }}
    .pill strong {{ color: #93c5fd; }}

    /* Comparator Section */
    .compare-container {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 28px;
    }}
    @media (max-width: 768px) {{
      .compare-container {{ grid-template-columns: 1fr; }}
    }}
    .compare-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      text-align: center;
    }}
    .compare-card h3 {{
      margin-bottom: 12px;
      font-size: 1.1rem;
      color: #94a3b8;
    }}
    .compare-card img {{
      width: 100%;
      aspect-ratio: 16/9;
      object-fit: cover;
      border-radius: 8px;
      border: 1px solid var(--border);
      cursor: pointer;
    }}

    /* Best Prompt Box */
    .best-box {{
      background: linear-gradient(135deg, rgba(59,130,246,0.1), rgba(16,185,129,0.1));
      border: 1px solid rgba(59,130,246,0.4);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 28px;
    }}
    .best-box-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}
    .best-box-title {{ font-size: 1.15rem; font-weight: 700; color: #34d399; }}
    .copy-btn {{
      background: #2563eb;
      color: white;
      border: none;
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      transition: background 0.2s;
    }}
    .copy-btn:hover {{ background: #1d4ed8; }}

    /* Iteration Cards */
    .iteration-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 20px;
    }}
    .iter-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 10px;
    }}
    .iter-title {{ font-size: 1.15rem; font-weight: 700; color: #f8fafc; }}
    .score-badge {{
      font-size: 0.95rem;
      font-weight: 700;
      padding: 4px 12px;
      border-radius: 6px;
    }}
    .score-high {{ background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #059669; }}
    .score-mid  {{ background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #d97706; }}
    .score-low  {{ background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid #dc2626; }}
    .score-rollback {{ background: rgba(239,68,68,0.25); color: #fca5a5; border: 1px solid #ef4444; margin-left: 6px; }}
    .score-best {{ background: rgba(16,185,129,0.25); color: #6ee7b7; border: 1px solid #10b981; margin-left: 6px; }}

    .iter-body {{
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 20px;
    }}
    @media (max-width: 880px) {{
      .iter-body {{ grid-template-columns: 1fr; }}
    }}
    .iter-media img {{
      width: 100%;
      aspect-ratio: 16/9;
      object-fit: cover;
      border-radius: 8px;
      border: 1px solid var(--border);
      cursor: pointer;
    }}
    .critique-box {{
      background: rgba(0,0,0,0.25);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 12px;
      font-size: 0.9rem;
    }}
    .critique-box strong {{ color: #cbd5e1; }}
    .critique-box p {{ color: #94a3b8; margin-top: 4px; }}
    .adj-list {{ margin: 8px 0 0 18px; color: #6ee7b7; font-size: 0.85rem; }}

    .prompt-label {{ font-size: 0.75rem; color: #64748b; font-weight: 700; text-transform: uppercase; margin-top: 8px; }}
    .prompt-text {{
      background: #111827;
      border: 1px solid #374151;
      border-radius: 6px;
      padding: 10px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      color: #e2e8f0;
      white-space: pre-wrap;
      word-break: break-all;
      margin-top: 4px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>🎯 AIVideo: Prompt 最佳化迭代成果</h1>
        <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">目標相似度門檻：{target_score}% | 模型：ComfyUI Z-Image Turbo</div>
      </div>
      <div class="meta-pills">
        <div class="pill">迭代輪數: <strong>{len(history)}</strong></div>
        <div class="pill">最佳相似度: <strong style="color: #34d399;">{best_score}%</strong></div>
      </div>
    </header>

    <div class="compare-container">
      <div class="compare-card">
        <h3>🎯 目標基準圖 (Target)</h3>
        <img src="{target_img_name}" alt="Target Image" onclick="window.open('{target_img_name}')">
      </div>
      <div class="compare-card">
        <h3>✨ 本次最佳成果 (Best Match - {best_score}%)</h3>
        <img src="{best_image}" alt="Best Result" onclick="window.open('{best_image}')">
      </div>
    </div>

    <div class="best-box">
      <div class="best-box-header">
        <div class="best-box-title">🏆 當前最佳 Prompt (達成 {best_score}% 相似度)</div>
        <button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('best-prompt-code').innerText); alert('已複製最佳 Prompt！');">複製 Prompt</button>
      </div>
      <pre id="best-prompt-code" class="prompt-text">{best_prompt}</pre>
    </div>

    <h2 style="font-size: 1.25rem; margin-bottom: 16px; color: #cbd5e1;">📋 歷次迭代演化歷史</h2>
    {"".join(reversed(cards_html))}
  </div>
</body>
</html>
"""
    html_path.write_text(full_html, encoding="utf-8")
    return html_path


def run_optimizer_internal(args: argparse.Namespace) -> int:
    """容器內部的優化迴圈執行本體。"""
    from aivideo.gemini_image import generate_image

    target_path = _normalize_repo_path(args.target_image)
    if not target_path.is_file():
        print(f"[錯誤] 找不到目標圖片：{target_path}", file=sys.stderr)
        return 1

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = REPO_ROOT / "jobs" / "_optimizer" / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # 複製一份目標圖片到該 run 目錄
    target_staged = run_dir / "target.png"
    shutil.copy2(target_path, target_staged)
    target_bytes = target_staged.read_bytes()

    print("==================================================================")
    print(f" 🚀 啟動 Prompt 最佳化迭代任務 (Run ID: {run_id})")
    print(f" 🎯 目標圖片: {target_path}")
    print(f" 🎯 目標相似度: {args.target_score}% | 最大迭代次數: {args.max_iterations}")
    print(f" 📁 成果儲存目錄: {run_dir}")
    print("==================================================================")

    min_w = float(getattr(args, "min_weight", 0.7) or 0.7)
    max_w = float(getattr(args, "max_weight", 1.3) or 1.3)

    current_prompt = clamp_prompt_weights(
        _clean_arg(args.prompt) or (
            "Character reference sheet, SINGLE character only, full-body standing pose, "
            "clear face, distinct hair, body proportions and signature outfit colors, "
            "clean minimalist neutral background, soft even lighting, 16:9 widescreen composition"
        ),
        min_weight=min_w,
        max_weight=max_w,
    )
    current_negative = clamp_prompt_weights(
        _clean_arg(args.negative_prompt) or (
            "(worst quality, low quality:1.4), rough lines, messy sketch, blur, deformed, "
            "bad anatomy, bad proportions, missing fingers, extra digits, signature, watermark, "
            "text, words, Chinese characters, subtitles, logos"
        ),
        min_weight=min_w,
        max_weight=max_w,
    )

    ref_image_arg = _clean_arg(args.ref_image)
    denoise_val = float(args.denoise or 0.75)

    # 隨機種子鎖定：若未指定則第 1 輪自動隨機產生一個 Seed，並在後續輪次全程固定，以徹底排除隨機變因干擾
    import random
    raw_seed = getattr(args, "seed", -1)
    actual_seed = int(raw_seed) if (raw_seed is not None and int(raw_seed) >= 0) else random.randint(1, 2**32 - 1)
    print(f" 🔒 已鎖定生成種子 (Seed): {actual_seed} (全程固定，確保只專注於 Prompt 變因調優)")
    print(f" 🛡️  Prompt 權重保護限制 (Clamp): [{min_w:.1f} ~ {max_w:.1f}] (防止權重失控過曝)")
    print(" 🔄 已啟用回退機制 (Rollback): 若新輪次走形，自動退回歷史最佳基準")

    history: list[dict[str, Any]] = []

    best_score = -1
    best_prompt = current_prompt
    best_negative = current_negative
    best_iteration = 0
    rollback_info = ""

    for i in range(1, args.max_iterations + 1):
        print(f"\n▶ [第 {i}/{args.max_iterations} 輪迭代] (Seed: {actual_seed}) 正在調用 ComfyUI (Z-Image Turbo) 生成中...")
        iter_img_name = f"iter_{i:03d}.png"
        iter_img_path = run_dir / iter_img_name

        try:
            generate_image(
                prompt=current_prompt,
                dest=iter_img_path,
                negative_prompt=current_negative,
                model="comfyui:z-image-turbo",
                aspect_ratio="16:9",
                ref_image=ref_image_arg if ref_image_arg else None,
                denoise=denoise_val,
                seed=actual_seed,
            )
        except Exception as gen_err:
            print(f"[錯誤] 第 {i} 輪生圖失敗: {gen_err}", file=sys.stderr)
            break

        if not iter_img_path.is_file():
            print(f"[錯誤] 生成檔案未成功寫入: {iter_img_path}", file=sys.stderr)
            break

        print(f"✔ 第 {i} 輪生成完成，正在呼叫 Vision AI 進行視覺比對與 Prompt 修正建議...")
        current_img_bytes = iter_img_path.read_bytes()

        eval_result = _evaluate_with_gemini_vision(
            target_img_bytes=target_bytes,
            current_img_bytes=current_img_bytes,
            current_prompt=current_prompt,
            current_negative=current_negative,
            rollback_info=rollback_info,
        )

        score = int(eval_result.get("similarity_score", 0))
        critique = eval_result.get("critique", "")
        key_adjs = eval_result.get("key_adjustments", [])
        raw_next_pos = eval_result.get("positive_prompt") or current_prompt
        raw_next_neg = eval_result.get("negative_prompt") or current_negative

        # 1. 對 AI 提出的下一輪 Prompt 進行硬性夾剪 (Clamp)
        next_pos = clamp_prompt_weights(raw_next_pos, min_weight=min_w, max_weight=max_w)
        next_neg = clamp_prompt_weights(raw_next_neg, min_weight=min_w, max_weight=max_w)

        print(f"★ 相似度評分: {score}%")
        print(f"  評語: {critique}")
        if key_adjs:
            for adj in key_adjs:
                print(f"  - {adj}")

        # 2. 回退機制判斷 (Rollback Mechanism)
        is_rollback = False
        if score > best_score:
            best_score = score
            best_prompt = current_prompt
            best_negative = current_negative
            best_iteration = i
            rollback_info = ""
            print(f"  🎉 突破歷史紀錄！創下當前最高相似度: {score}%")
        elif best_iteration > 0 and score < best_score:
            is_rollback = True
            print(f"  ⚠️ [觸發回退機制 Rollback] 當前分數 ({score}%) 低於歷史最佳 ({best_score}%，第 {best_iteration} 輪)！")
            print(f"     已放棄劣化的修改方向，下輪基準自動回退至第 {best_iteration} 輪最佳 Prompt。")
            rollback_info = (
                f"Iteration {i} caused similarity score to drop from {best_score}% down to {score}%. "
                f"That modification was rejected and ROLLED BACK to Iteration #{best_iteration} baseline. "
                f"Please take a more subtle, different approach without repeating the failed changes."
            )

        history.append({
            "iteration": i,
            "image": iter_img_name,
            "similarity_score": score,
            "prompt": current_prompt,
            "negative_prompt": current_negative,
            "critique": critique,
            "key_adjustments": key_adjs,
            "rollback": is_rollback,
            "is_best": (i == best_iteration),
        })

        # 即時更新 HTML 儀表板與 JSON 紀錄
        (run_dir / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        html_file = _render_review_html(run_dir, "target.png", history, args.target_score)

        # 同步維護 latest_review.html
        latest_html = REPO_ROOT / "jobs" / "_optimizer" / "latest_review.html"
        try:
            shutil.copy2(html_file, latest_html)
        except Exception:
            pass

        if score >= args.target_score:
            print(f"\n🎉 成功達到目標相似度門檻 ({score}% >= {args.target_score}%)！提前結束迭代。")
            break

        # 根據回退機制決定下一輪 Prompt
        if is_rollback:
            current_prompt = clamp_prompt_weights(best_prompt, min_weight=min_w, max_weight=max_w)
            current_negative = clamp_prompt_weights(best_negative, min_weight=min_w, max_weight=max_w)
        else:
            current_prompt = next_pos
            current_negative = next_neg

    best_item = max(history, key=lambda x: x["similarity_score"]) if history else None
    print("\n==================================================================")
    print(" 🏁 Prompt 最佳化迭代任務完成！")
    if best_item:
        print(f" 🏆 最高相似度: {best_item['similarity_score']}% (第 {best_item['iteration']} 輪)")
        print(f" 🏆 最佳正面提示詞:\n{best_item['prompt']}")
    print(f" 📊 可檢視的 Review 儀表板: {run_dir / 'review.html'}")
    print("==================================================================")
    return 0


# ==============================================================================
# Host 端啟動包裝器 (Host Launcher)
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="自動化最佳 Prompt 迭代任務")
    parser.add_argument("--target-image", required=True, help="目標對齊圖片路徑")
    parser.add_argument("--prompt", nargs="*", default=None, help="初始正面提示詞")
    parser.add_argument("--negative-prompt", nargs="*", default=None, help="初始負面提示詞")
    parser.add_argument("--max-iterations", type=int, default=5, help="最大迭代次數 (預設 5)")
    parser.add_argument("--target-score", type=int, default=99, help="目標相似度百分比 (預設 99)")
    parser.add_argument("--ref-image", nargs="?", const="", default="", help="可選圖生圖參考圖")
    parser.add_argument("--denoise", nargs="?", const=0.75, type=float, default=0.75, help="重繪強度")
    parser.add_argument("--seed", type=int, default=-1, help="固定隨機種子 (-1 為自動鎖定首輪 Seed)")
    parser.add_argument("--max-weight", type=float, default=1.3, help="Prompt 權重硬性夾剪上限 (預設 1.3)")
    parser.add_argument("--min-weight", type=float, default=0.7, help="Prompt 權重硬性夾剪下限 (預設 0.7)")
    parser.add_argument("--internal-docker", action="store_true", help="內部 Docker 執行標記")
    args = parser.parse_args()

    # 1. 若已經在容器內，直接執行優化主邏輯
    if _is_in_docker() or args.internal_docker:
        return run_optimizer_internal(args)

    # 2. 若在 Host 端，將工作派發至 pipeline 容器執行
    clean_target = _clean_arg(args.target_image)
    target_path = Path(clean_target)
    if not target_path.is_absolute():
        target_path = REPO_ROOT / target_path

    # 相對於 REPO_ROOT 轉換路徑供容器內訪問
    try:
        rel_target = str(target_path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        # 目標圖若在外部，先拷貝至 jobs/_smoke/ 供容器存取
        smoke_dir = REPO_ROOT / "jobs" / "_smoke"
        smoke_dir.mkdir(parents=True, exist_ok=True)
        rel_target = f"jobs/_smoke/{target_path.name}"
        shutil.copy2(target_path, REPO_ROOT / rel_target)

    cmd = [
        "docker",
        "compose",
        "run",
        "--rm",
        "-e",
        "PYTHONPATH=/workspace",
        "pipeline",
        "python",
        "-u",
        "scripts/optimize_prompt.py",
        "--internal-docker",
        "--target-image",
        rel_target,
        "--max-iterations",
        str(args.max_iterations),
        "--target-score",
        str(args.target_score),
        "--seed",
        str(args.seed),
        "--max-weight",
        str(args.max_weight),
        "--min-weight",
        str(args.min_weight),
    ]

    p_val = _clean_arg(args.prompt)
    if p_val:
        cmd.extend(["--prompt", p_val])
    n_val = _clean_arg(args.negative_prompt)
    if n_val:
        cmd.extend(["--negative-prompt", n_val])
    r_val = _clean_arg(args.ref_image)
    if r_val:
        cmd.extend(["--ref-image", r_val, "--denoise", str(args.denoise)])

    print("==========================================================")
    print(" 正在透過 Docker 容器執行自動化 Prompt 最佳化迭代任務...")
    print(f" 目標圖片: {clean_target}")
    print(f" 相似度門檻: {args.target_score}% | 最大輪數: {args.max_iterations}")
    print("==========================================================")

    ret = subprocess.run(cmd, cwd=REPO_ROOT)

    # 執行完畢後嘗試在 VS Code / 預設瀏覽器開啟最新 review 報告
    latest_review = REPO_ROOT / "jobs" / "_optimizer" / "latest_review.html"
    if latest_review.is_file():
        import webbrowser
        try:
            webbrowser.open(latest_review.as_uri())
            print(f"\n[完成] 已在瀏覽器開啟最新迭代 Review 儀表板：\n  {latest_review}")
        except Exception:
            pass

    return ret.returncode


if __name__ == "__main__":
    sys.exit(main() or 0)

