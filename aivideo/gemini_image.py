from __future__ import annotations

import os
from pathlib import Path


SMOKE_PROMPT = (
    "電影感靜幀，16:9 橫式構圖，下雨的城市巷口，地面反光，"
    "一盞暖色路燈，沒有行人，膠片顆粒，低光照。不要任何文字或浮水印。"
)

# 金鑰能用哪個 id 因帳號而異；由新到舊試。
MODEL_CANDIDATES = (
    "gemini-3.1-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
)


def generate_smoke_image(dest: Path) -> Path:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY")

    preferred = os.environ.get("GEMINI_IMAGE_MODEL", "").strip()
    models = [preferred] if preferred else []
    for name in MODEL_CANDIDATES:
        if name not in models:
            models.append(name)

    image_size = os.environ.get("GEMINI_IMAGE_SIZE", "1K")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "容器裡沒有 google-genai。請執行：pip install -e . "
            "或重建映像 docker compose build pipeline"
        ) from exc

    client = genai.Client(api_key=api_key)
    errors: list[str] = []

    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=SMOKE_PROMPT,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9",
                        image_size=image_size,
                    ),
                ),
            )
        except Exception as exc:  # noqa: BLE001 — 要對使用者顯示 API 原文
            message = str(exc)
            if "free_tier" in message and "limit: 0" in message:
                raise RuntimeError(_quota_help(model, message)) from exc
            errors.append(f"{model}: {message}")
            continue

        data = _first_image_bytes(response)
        if data:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return dest

        text = _first_text(response)
        errors.append(f"{model}: 有回應但沒有圖片" + (f"；模型說：{text[:300]}" if text else ""))

    raise RuntimeError(
        "Gemini 無法產出 16:9 圖。\n" + "\n".join(errors)
    )


def _quota_help(model: str, raw: str) -> str:
    return (
        f"{model} 回 429：這把 API 金鑰走的是「免費層」，影像模型配額是 0。\n"
        "Google AI Pro（Gemini App／網頁）跟 Gemini API 計費是分開的；"
        "ComfyUI／本 CLI 走的是 API。\n"
        "請到 AI Studio 看這把 key 綁哪個 Cloud 專案，並為該專案開計費：\n"
        "  https://aistudio.google.com/apikey\n"
        "  https://ai.google.dev/gemini-api/docs/billing\n"
        "  https://ai.dev/rate-limit\n"
        "開好後再跑：docker compose run --rm pipeline python -m aivideo check --gemini\n"
        f"（原文摘要）{raw[:400]}"
    )


def _first_text(response: object) -> str:
    chunks: list[str] = []
    for part in _iter_parts(response):
        text = getattr(part, "text", None)
        if text:
            chunks.append(str(text))
    return "\n".join(chunks).strip()


def _first_image_bytes(response: object) -> bytes | None:
    for part in _iter_parts(response):
        inline = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
        raw = _blob_bytes(inline)
        if raw:
            return raw

        as_image = getattr(part, "as_image", None)
        if callable(as_image):
            image = as_image()
            converted = _sdk_image_bytes(image)
            if converted:
                return converted
    return None


def _blob_bytes(blob: object | None) -> bytes | None:
    if blob is None:
        return None
    payload = getattr(blob, "data", None)
    if payload is None:
        payload = getattr(blob, "image_bytes", None)
    if payload is None:
        return None
    if isinstance(payload, bytes):
        return payload
    import base64

    return base64.b64decode(payload)


def _sdk_image_bytes(image: object | None) -> bytes | None:
    if image is None:
        return None
    raw = _blob_bytes(image)
    if raw:
        return raw
    save = getattr(image, "save", None)
    if not callable(save):
        return None
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
    try:
        save(path)
        return Path(path).read_bytes()
    finally:
        Path(path).unlink(missing_ok=True)


def _iter_parts(response: object):
    parts = list(getattr(response, "parts", None) or [])
    if not parts:
        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            parts.extend(getattr(content, "parts", None) or [])
    yield from parts
