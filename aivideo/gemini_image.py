from __future__ import annotations

import os
from pathlib import Path


_VERTEX_ENV_KEYS = (
    ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_PROJECT"),
    ("VERTEX_PROJECT_ID", "GOOGLE_CLOUD_PROJECT"),
    ("GOOGLE_CLOUD_LOCATION", "GOOGLE_CLOUD_LOCATION"),
    ("GOOGLE_CLOUD_REGION", "GOOGLE_CLOUD_LOCATION"),
    ("VERTEX_LOCATION", "GOOGLE_CLOUD_LOCATION"),
)

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


def get_gemini_client_kwargs() -> dict[str, object]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    vertex_mode = str(os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # 若有 GEMINI_API_KEY，且沒有外部 ADC service account 憑證檔，以 API Key (Google AI Studio) 為主
    # 並顯式將 GOOGLE_GENAI_USE_VERTEXAI 設為 false，避免 SDK 誤走 Vertex AI
    if api_key and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
        return {"api_key": api_key}

    if vertex_mode:
        project = _env_value("GOOGLE_CLOUD_PROJECT") or _env_value("VERTEX_PROJECT_ID")
        location = _env_value("GOOGLE_CLOUD_LOCATION") or _env_value("GOOGLE_CLOUD_REGION") or _env_value("VERTEX_LOCATION")
        if not project or not location:
            raise RuntimeError(
                "Vertex AI 模式已啟用，但缺少 GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION（或 VERTEX_*）。"
            )
        return {"vertexai": True, "project": project, "location": location}

    if api_key:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
        return {"api_key": api_key}

    raise RuntimeError(
        "缺少 Gemini 認證：請設定 GEMINI_API_KEY，或啟用 Vertex AI（GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION）。"
    )


def has_gemini_credentials() -> bool:
    try:
        get_gemini_client_kwargs()
        return True
    except RuntimeError:
        return False


def _env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def generate_smoke_image(dest: Path) -> Path:
    dest, _, _ = generate_image(prompt=SMOKE_PROMPT, dest=dest)
    return dest


def generate_image(
    prompt: str,
    dest: Path,
    aspect_ratio: str = "16:9",
    image_size: str = "1K",
    model: str | None = None,
    seed: int | None = None,
) -> tuple[Path, str, int | None]:
    preferred = (model or os.environ.get("GEMINI_IMAGE_MODEL", "")).strip()
    models = [preferred] if preferred else []
    for name in MODEL_CANDIDATES:
        if name not in models:
            models.append(name)

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "容器裡沒有 google-genai。請執行：pip install -e '.[dev]' "
            "或重建映像 docker compose build pipeline"
        ) from exc

    try:
        client_kwargs = get_gemini_client_kwargs()
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc

    client = genai.Client(**client_kwargs)
    errors: list[str] = []

    for m in models:
        try:
            image_config = types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
            config_kwargs: dict[str, object] = {
                "response_modalities": ["TEXT", "IMAGE"],
                "image_config": image_config,
            }
            if seed is not None:
                config_kwargs["seed"] = seed

            config = types.GenerateContentConfig(**config_kwargs)

            response = client.models.generate_content(
                model=m,
                contents=prompt,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 — 要對使用者顯示 API 原文
            message = str(exc)
            if "free_tier" in message and "limit: 0" in message:
                raise RuntimeError(_quota_help(m, message)) from exc
            errors.append(f"{m}: {message}")
            continue

        data = _first_image_bytes(response)
        if data:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return dest, m, seed

        text = _first_text(response)
        errors.append(f"{m}: 有回應但沒有圖片" + (f"；模型說：{text[:300]}" if text else ""))

    raise RuntimeError(
        "Gemini 無法產出圖。\n" + "\n".join(errors)
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
