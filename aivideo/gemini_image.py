from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

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
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
    "gemini-3.1-flash-image",
    "gemini-3.1-flash-image-preview",
    "imagen-3.0-generate-002",
)


def get_gemini_client_kwargs() -> dict[str, object]:
    from aivideo.commands.check import _load_dotenv
    _load_dotenv()

    vertex_mode = str(os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # 若專案目錄下有 .gcloud/application_default_credentials.json，自動設置環境變數供 Google SDK 讀取
    default_adc_path = REPO_ROOT / ".gcloud" / "application_default_credentials.json"
    if default_adc_path.is_file() and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(default_adc_path)

    # 1. 優先支援 Vertex AI 模式
    if vertex_mode:
        project = _env_value("GOOGLE_CLOUD_PROJECT") or _env_value("VERTEX_PROJECT_ID")
        location = _env_value("GOOGLE_CLOUD_LOCATION") or _env_value("GOOGLE_CLOUD_REGION") or _env_value("VERTEX_LOCATION") or "us-central1"
        if not project:
            raise RuntimeError(
                "Vertex AI 模式已啟用，但缺少 GOOGLE_CLOUD_PROJECT / VERTEX_PROJECT_ID。"
            )
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        return {"vertexai": True, "project": project, "location": location}

    # 2. 次要支援 Google AI Studio API Key 模式
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
        return {"api_key": api_key}

    # 若未指定 Vertex 且無 API Key，但有 ADC 憑證與專案，自動回退至 Vertex AI
    project = _env_value("GOOGLE_CLOUD_PROJECT") or _env_value("VERTEX_PROJECT_ID")
    location = _env_value("GOOGLE_CLOUD_LOCATION") or "us-central1"
    if project and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        return {"vertexai": True, "project": project, "location": location}

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
    ref_image: Path | bytes | None = None,
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

    # 處理參考圖輸入（Image Reference Conditioning）
    ref_part = None
    if ref_image:
        if isinstance(ref_image, (str, Path)):
            p = Path(ref_image)
            if p.is_file():
                mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
                ref_part = types.Part.from_bytes(data=p.read_bytes(), mime_type=mime)
        elif isinstance(ref_image, bytes) and ref_image:
            ref_part = types.Part.from_bytes(data=ref_image, mime_type="image/png")

    if ref_part is not None:
        contents: object = [
            ref_part,
            f"Visual Reference: The attached image defines the primary visual subject/character appearance and structural details. Maintain strict visual consistency with the subject shown in the reference image while rendering the following new 16:9 widescreen scene:\n{prompt}",
        ]
    else:
        contents = prompt

    for m in models:
        max_attempts = 4
        response = None
        for attempt in range(1, max_attempts + 1):
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
                    contents=contents,
                    config=config,
                )
                break
            except Exception as exc:  # noqa: BLE001 — 要對使用者顯示 API 原文
                message = str(exc)
                if "free_tier" in message and "limit: 0" in message:
                    raise RuntimeError(_quota_help(m, message)) from exc

                is_429 = "429" in message or "RESOURCE_EXHAUSTED" in message or "resource exhausted" in message.lower()
                if is_429 and attempt < max_attempts:
                    import time
                    backoff_sec = attempt * 8  # 8s, 16s, 24s
                    print(f"[warn] {m} 觸發 Google 速率限制 (429)，自動等待 {backoff_sec} 秒後重試 (第 {attempt}/{max_attempts-1} 次)...")
                    time.sleep(backoff_sec)
                    continue
                else:
                    errors.append(f"{m}: {message}")
                    break

        if response is None:
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
