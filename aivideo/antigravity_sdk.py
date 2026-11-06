from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

ANTIGRAVITY_SDK_PREFIXES = ("antigravity-sdk:", "ag-sdk:")


def has_antigravity_sdk() -> bool:
    """檢查當前 Python 環境是否已安裝官方 google-antigravity SDK。"""
    try:
        import google.antigravity  # noqa: F401

        return True
    except ImportError:
        return False


def is_antigravity_sdk_enabled(model_name: str | None = None, backend: str | None = None) -> bool:
    """判斷當次呼叫是否應走 Antigravity SDK 模式。

    觸發條件（擇一）：
    1. 模型名稱帶有 `antigravity-sdk:` 或 `ag-sdk:` 前綴，或為 `antigravity-sdk`
    2. backend 明確指定為 `antigravity` 或 `antigravity-sdk`
    3. 環境變數 `AIVIDEO_USE_ANTIGRAVITY_SDK=true`
    """
    from aivideo.commands.check import _load_dotenv

    _load_dotenv()
    m = (model_name or "").strip().lower()
    if m in ("antigravity-sdk", "ag-sdk") or any(m.startswith(p) for p in ANTIGRAVITY_SDK_PREFIXES):
        return True
    b = (backend or "").strip().lower()
    if b in ("antigravity", "antigravity-sdk", "ag-sdk"):
        return True
    env_flag = str(os.environ.get("AIVIDEO_USE_ANTIGRAVITY_SDK", "")).strip().lower()
    return env_flag in {"1", "true", "yes", "on"}


def unwrap_antigravity_model_name(model_name: str | None, default_model: str) -> str:
    """去除 `antigravity-sdk:` 前綴，還原底層實際 Gemini 模型名稱。"""
    raw = (model_name or "").strip()
    if not raw or raw.lower() in ("antigravity-sdk", "ag-sdk"):
        return default_model
    lower = raw.lower()
    for prefix in ANTIGRAVITY_SDK_PREFIXES:
        if lower.startswith(prefix):
            stripped = raw[len(prefix) :].strip()
            return stripped if stripped else default_model
    return raw


def _run_coro_sync(coro: Any) -> Any:
    """在同步函式中安全執行 async coroutine（相容已有運轉中 Event Loop 的 FastAPI 環境）。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    return asyncio.run(coro)


def _build_sdk_endpoint(model_name: str, location_override: str | None = None) -> Any:
    """根據當前 .env / 憑證配置，建構 Antigravity SDK 的 VertexEndpoint 或 GeminiAPIEndpoint。"""
    from google.antigravity import types as ag_types
    from aivideo.gemini_image import get_gemini_client_kwargs

    client_kwargs = get_gemini_client_kwargs(model=model_name, location=location_override)
    if client_kwargs.get("vertexai"):
        return ag_types.VertexEndpoint(
            project=str(client_kwargs.get("project") or ""),
            location=str(location_override or client_kwargs.get("location") or "global"),
        )
    api_key = str(client_kwargs.get("api_key") or os.environ.get("GEMINI_API_KEY", "")).strip()
    return ag_types.GeminiAPIEndpoint(api_key=api_key)


def generate_text_via_antigravity_sdk(
    prompt: str,
    model: str | None = None,
    *,
    system_instructions: str | None = None,
    search_grounding: bool = False,
    json_mode: bool = False,
    response_schema: dict[str, Any] | str | None = None,
) -> str:
    """透過官方 google-antigravity SDK 執行文字生成（支援 Google Search Grounding 與 JSON 輸出，並預設關閉遙測追蹤）。"""
    if not has_antigravity_sdk():
        raise RuntimeError(
            "尚未安裝 google-antigravity SDK。請執行 dev-kit 任務「安裝官方 google-antigravity SDK」"
            "或在容器內執行：pip install google-antigravity"
        )

    from google.antigravity import (
        Agent,
        AgentBehavior,
        BuiltinTools,
        CapabilitiesConfig,
        LocalAgentConfig,
        ModelTarget,
        ModelType,
    )
    from google.antigravity.connections.connection import DebugConfig

    resolved_model = unwrap_antigravity_model_name(model, "gemini-3.8-flash")
    candidate_models = [resolved_model]
    for fallback_m in ("gemini-3.6-flash", "gemini-2.5-flash"):
        if fallback_m not in candidate_models:
            candidate_models.append(fallback_m)

    enabled_tools = [BuiltinTools.SEARCH_WEB] if search_grounding else []
    sys_inst = system_instructions or (
        "You are a deterministic generation engine. Return ONLY the requested output without conversational filler."
    )
    if json_mode and not response_schema:
        sys_inst += "\nIMPORTANT: Output MUST be valid raw JSON only. Do not wrap in explanations."

    # 明確關閉 Server-side tracing 遙測
    debug_cfg = DebugConfig(enable_server_side_tracing=False, logging_level=logging.WARNING)

    async def _run_single(target_model: str) -> str:
        endpoint = _build_sdk_endpoint(target_model)
        with tempfile.TemporaryDirectory(prefix="ag_text_") as tmp_dir:
            cfg = LocalAgentConfig(
                system_instructions=sys_inst,
                models=[
                    ModelTarget(
                        name=target_model,
                        types=[ModelType.TEXT],
                        endpoint=endpoint,
                    )
                ],
                capabilities=CapabilitiesConfig(
                    enabled_tools=enabled_tools,
                    enable_subagents=False,
                    agent_behavior=AgentBehavior.MINIMAL,
                ),
                response_schema=response_schema,
                save_dir=tmp_dir,
                app_data_dir=tmp_dir,
                debug_config=debug_cfg,
            )
            async with Agent(cfg) as agent:
                resp = await agent.chat(prompt)
                text = await resp.text()
                if not text and response_schema:
                    structured = await resp.structured_output()
                    if structured is not None:
                        import json

                        return json.dumps(structured, ensure_ascii=False)
                return (text or "").strip()

    last_err: Exception | None = None
    for cand in candidate_models:
        try:
            out = _run_coro_sync(_run_single(cand))
            if out:
                return out
        except Exception as exc:
            last_err = exc
            err_s = str(exc)
            if err_s.startswith("Antigravity SDK 未產生圖片檔案"):
                raise
            if "429" in err_s or "RESOURCE_EXHAUSTED" in err_s or "quota" in err_s.lower() or "404" in err_s:
                continue
            raise
    if last_err:
        raise last_err
    return ""


def generate_image_via_antigravity_sdk(
    prompt: str,
    dest: Path,
    *,
    aspect_ratio: str = "16:9",
    model: str | None = None,
    seed: int | None = None,
    ref_image: Path | bytes | None = None,
    ref_images: list[Path | bytes | tuple[Path | bytes, str]] | None = None,
    location: str | None = None,
) -> tuple[Path, str, int | None]:
    """透過官方 google-antigravity SDK 的內建 GENERATE_IMAGE 工具與 ModelType.IMAGE 模型生成圖片。"""
    if not has_antigravity_sdk():
        raise RuntimeError(
            "尚未安裝 google-antigravity SDK。請執行 dev-kit 任務「安裝官方 google-antigravity SDK」"
            "或在容器內執行：pip install google-antigravity"
        )

    from google.antigravity import (
        Agent,
        AgentBehavior,
        BuiltinTools,
        CapabilitiesConfig,
        Image as AgImage,
        LocalAgentConfig,
        ModelTarget,
        ModelType,
    )
    from google.antigravity.connections.connection import DebugConfig
    from google.antigravity.types import ToolResult
    from aivideo.naming import DEFAULT_IMAGE_MODEL

    resolved_img_model = unwrap_antigravity_model_name(model, DEFAULT_IMAGE_MODEL)
    driver_candidates = ("gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.8-flash")
    img_endpoint = _build_sdk_endpoint(resolved_img_model, location_override=location)

    # 整理參考圖片 (Reference Images)
    raw_refs: list[Path | bytes | tuple[Path | bytes, str]] = []
    if ref_images:
        raw_refs.extend(ref_images)
    elif ref_image is not None:
        raw_refs.append(ref_image)

    import hashlib

    media_parts: list[Any] = []
    labels: list[str] = []
    input_hashes: set[str] = set()
    for idx, item in enumerate(raw_refs, start=1):
        label = ""
        src: Path | bytes
        if isinstance(item, tuple) and len(item) == 2:
            src, label = item[0], str(item[1] or "").strip()
        else:
            src = item  # type: ignore[assignment]
        if not label:
            label = f"character reference {idx}"

        img_bytes: bytes | None = None
        mime = "image/png"
        if isinstance(src, (str, Path)):
            p = Path(src)
            if p.is_file():
                img_bytes = p.read_bytes()
                suf = p.suffix.lower()
                mime = "image/png" if suf == ".png" else "image/webp" if suf == ".webp" else "image/jpeg"
        elif isinstance(src, bytes) and src:
            img_bytes = src

        if img_bytes:
            input_hashes.add(hashlib.sha256(img_bytes).hexdigest())
            media_parts.append(AgImage(data=img_bytes, mime_type=mime, description=label))
            labels.append(label)

    # 明確關閉 Server-side tracing 遙測
    debug_cfg = DebugConfig(enable_server_side_tracing=False, logging_level=logging.WARNING)

    async def _run_with_driver(text_driver_model: str) -> Path:
        txt_endpoint = _build_sdk_endpoint(text_driver_model)
        with tempfile.TemporaryDirectory(prefix="ag_img_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            out_dir = tmp_path / "outputs"
            app_dir = tmp_path / "appdata"
            out_dir.mkdir(parents=True, exist_ok=True)
            app_dir.mkdir(parents=True, exist_ok=True)

            cfg = LocalAgentConfig(
                system_instructions=(
                    "You are an automated image generation agent. "
                    "Immediately call the `generate_image` tool once with the requested prompt and aspect ratio "
                    f"('{aspect_ratio}'), and image_name='scene_output'. Do not ask questions."
                ),
                models=[
                    ModelTarget(
                        name=text_driver_model,
                        types=[ModelType.TEXT],
                        endpoint=txt_endpoint,
                    ),
                    ModelTarget(
                        name=resolved_img_model,
                        types=[ModelType.IMAGE],
                        endpoint=img_endpoint,
                    ),
                ],
                capabilities=CapabilitiesConfig(
                    enabled_tools=[BuiltinTools.GENERATE_IMAGE],
                    enable_subagents=False,
                    agent_behavior=AgentBehavior.AUTONOMOUS,
                ),
                save_dir=str(out_dir),
                app_data_dir=str(app_dir),
                debug_config=debug_cfg,
            )

            task_prompt = (
                f"Call `generate_image` with aspect_ratio='{aspect_ratio}', image_name='scene_output', "
                f"and the following visual prompt:\n{prompt}"
            )
            if labels:
                ref_note = ", ".join(labels)
                task_prompt = (
                    f"Use the attached reference image(s) ({ref_note}) to maintain exact character/entity visual consistency. "
                    + task_prompt
                )

            chat_input: Any = [*media_parts, task_prompt] if media_parts else task_prompt

            async with Agent(cfg) as agent:
                resp = await agent.chat(chat_input)
                chunks = await resp.resolve()

                tool_errors: list[str] = []
                # 1. 優先從 ToolResult 的 GenerateImageResult.output_path 取得生圖路徑
                for ch in chunks:
                    if isinstance(ch, ToolResult):
                        if getattr(ch, "error", None):
                            tool_errors.append(str(ch.error))
                        if ch.result is not None:
                            out_p = getattr(ch.result, "output_path", None)
                            if not out_p and isinstance(ch.result, dict):
                                out_p = ch.result.get("output_path") or ch.result.get("path")
                            if out_p and Path(str(out_p)).is_file():
                                p_cand = Path(str(out_p))
                                if hashlib.sha256(p_cand.read_bytes()).hexdigest() not in input_hashes:
                                    dest.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(p_cand, dest)
                                    return dest

                # 2. 備援：僅掃描輸出目錄或檔名開頭為 scene_output 的生成檔，並排除輸入參考圖 (定裝圖)
                candidates_found: list[Path] = []
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                    candidates_found.extend(out_dir.rglob(ext))
                candidates_found.extend(app_dir.rglob("scene_output*"))

                valid_outputs = [
                    p
                    for p in candidates_found
                    if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() not in input_hashes
                ]
                if valid_outputs:
                    newest = max(valid_outputs, key=lambda p: p.stat().st_mtime)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(newest, dest)
                    return dest

                text_reply = "".join(
                    getattr(c, "text", "") for c in chunks if hasattr(c, "text")
                ).strip()
                err_detail = "；".join(tool_errors) if tool_errors else text_reply[:240]
                raise RuntimeError(
                    f"Antigravity SDK 未產生圖片檔案 ({resolved_img_model})"
                    + (f"：{err_detail}" if err_detail else "")
                )

    last_err: Exception | None = None
    saved_dest: Path | None = None
    for driver_m in driver_candidates:
        try:
            saved_dest = _run_coro_sync(_run_with_driver(driver_m))
            break
        except Exception as exc:
            last_err = exc
            err_s = str(exc)
            if err_s.startswith("Antigravity SDK 未產生圖片檔案"):
                raise
            if "429" in err_s or "RESOURCE_EXHAUSTED" in err_s or "quota" in err_s.lower() or "404" in err_s:
                continue
            raise
    if saved_dest is None:
        if last_err:
            raise last_err
        raise RuntimeError(f"Antigravity SDK 生圖失敗 ({resolved_img_model})")
    return saved_dest, f"antigravity-sdk:{resolved_img_model}", seed

