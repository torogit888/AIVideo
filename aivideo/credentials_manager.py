from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS_DIR = REPO_ROOT / "assets" / "credentials"
ACCOUNTS_FILE = CREDENTIALS_DIR / "vertex_accounts.json"
CACHE_FILE = CREDENTIALS_DIR / "models_cache.json"

# 常見需要檢查狀態的文本與生圖模型
KNOWN_TEXT_MODELS = [
    {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash"},
    {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash"},
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
    {"id": "grok-4.7", "name": "xAI Grok 4.7"},
]

KNOWN_IMAGE_MODELS = [
    {"id": "gemini-3.1-flash-image", "name": "Gemini 3.1 Flash Image"},
    {"id": "gemini-3-pro-image", "name": "Gemini 3 Pro Image"},
    {"id": "gemini-2.5-flash-image", "name": "Gemini 2.5 Flash Image"},
    {"id": "imagen-3.0-generate-002", "name": "Imagen 3 (002)"},
]


def _ensure_dir():
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)


def _load_accounts_data() -> Dict[str, Any]:
    _ensure_dir()
    if ACCOUNTS_FILE.is_file():
        try:
            return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 若尚未建立 accounts.json，從現有 .env 自動初始化出第一筆預設帳號
    return _init_default_account_from_env()


def _save_accounts_data(data: Dict[str, Any]):
    _ensure_dir()
    ACCOUNTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _init_default_account_from_env() -> Dict[str, Any]:
    from aivideo.commands.check import _load_dotenv
    _load_dotenv()

    use_vertex = str(os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "")).strip().lower() in {"1", "true", "yes", "on"}
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("VERTEX_PROJECT_ID", "")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION") or os.environ.get("VERTEX_LOCATION", "us-central1")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    client_email = ""
    auth_type = "service_account" if use_vertex else ("api_key" if api_key else "adc")

    if cred_path:
        # 嘗試讀取 service account 的 email
        try:
            p = Path(cred_path)
            if p.is_file():
                sa_data = json.loads(p.read_text(encoding="utf-8"))
                client_email = sa_data.get("client_email", "")
                if not project_id:
                    project_id = sa_data.get("project_id", "")
        except Exception:
            pass

    now_iso = datetime.now().isoformat()
    acc_id = "default"
    default_acc = {
        "id": acc_id,
        "name": f"預設帳戶 ({project_id or 'Vertex AI'})" if project_id else "預設帳戶",
        "auth_type": auth_type,
        "project_id": project_id,
        "location": location,
        "credentials_file": cred_path,
        "client_email": client_email,
        "api_key_masked": (api_key[:6] + "..." + api_key[-4:]) if len(api_key) > 10 else ("已設定" if api_key else ""),
        "api_key_raw": api_key,
        "is_active": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    initial_data = {
        "active_account_id": acc_id,
        "accounts": [default_acc],
    }
    _save_accounts_data(initial_data)
    return initial_data


def list_accounts() -> List[Dict[str, Any]]:
    data = _load_accounts_data()
    active_id = data.get("active_account_id", "")
    result = []
    for a in data.get("accounts", []):
        item = dict(a)
        # 絕不把未遮罩的 api_key 或機密私鑰直接傳回前端
        item.pop("api_key_raw", None)
        item["is_active"] = (item.get("id") == active_id)
        result.append(item)
    return result


def get_active_account() -> Optional[Dict[str, Any]]:
    data = _load_accounts_data()
    active_id = data.get("active_account_id")
    for a in data.get("accounts", []):
        if a.get("id") == active_id:
            return a
    if data.get("accounts"):
        return data["accounts"][0]
    return None


def create_account(
    name: str,
    auth_type: str = "service_account",
    project_id: str = "",
    location: str = "us-central1",
    service_account_json: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    _ensure_dir()
    data = _load_accounts_data()

    acc_id = f"acc_{int(time.time())}"
    now_iso = datetime.now().isoformat()
    client_email = ""
    cred_file_path = ""

    # 處理 Service Account JSON
    if auth_type == "service_account" and service_account_json and service_account_json.strip():
        try:
            parsed = json.loads(service_account_json)
            client_email = parsed.get("client_email", "")
            if not project_id:
                project_id = parsed.get("project_id", "")
            # 存成專屬金鑰檔 assets/credentials/{acc_id}.json
            file_name = f"{acc_id}_credentials.json"
            save_path = CREDENTIALS_DIR / file_name
            save_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
            # 支援容器路徑與宿主機路徑智能適配
            cred_file_path = f"assets/credentials/{file_name}"
        except Exception as e:
            raise ValueError(f"Service Account JSON 格式錯誤: {str(e)}")

    api_key_val = (api_key or "").strip()
    api_key_masked = ""
    if api_key_val:
        api_key_masked = (api_key_val[:6] + "..." + api_key_val[-4:]) if len(api_key_val) > 10 else "已設定"

    account = {
        "id": acc_id,
        "name": name.strip() or f"帳戶-{acc_id[-4:]}",
        "auth_type": auth_type,
        "project_id": project_id.strip(),
        "location": location.strip() or "us-central1",
        "credentials_file": cred_file_path,
        "client_email": client_email,
        "api_key_masked": api_key_masked,
        "api_key_raw": api_key_val,
        "is_active": False,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    data.setdefault("accounts", []).append(account)
    _save_accounts_data(data)
    return account


def activate_account(account_id: str) -> Dict[str, Any]:
    """切換並立即啟用指定的 Vertex AI / Google 帳戶憑證。"""
    data = _load_accounts_data()
    target = None
    for a in data.get("accounts", []):
        if a.get("id") == account_id:
            target = a
            break

    if not target:
        raise ValueError(f"找不到指定帳戶: {account_id}")

    data["active_account_id"] = account_id
    _save_accounts_data(data)

    # 同步寫入 .env 並即時更新 os.environ
    _apply_account_to_environment(target)
    return target


def delete_account(account_id: str) -> bool:
    data = _load_accounts_data()
    accounts = data.get("accounts", [])
    if data.get("active_account_id") == account_id and len(accounts) > 1:
        raise ValueError("無法刪除當前使用中的作用中帳戶，請先切換至其他帳戶再刪除。")

    target = None
    new_accounts = []
    for a in accounts:
        if a.get("id") == account_id:
            target = a
        else:
            new_accounts.append(a)

    if not target:
        return False

    # 若有本機 json 金鑰檔，一併清理
    if target.get("credentials_file"):
        try:
            rel = target["credentials_file"]
            p = REPO_ROOT / rel if not Path(rel).is_absolute() else Path(rel)
            if p.is_file() and p.name.startswith("acc_"):
                p.unlink(missing_ok=True)
        except Exception:
            pass

    data["accounts"] = new_accounts
    if data.get("active_account_id") == account_id and new_accounts:
        data["active_account_id"] = new_accounts[0]["id"]
        _apply_account_to_environment(new_accounts[0])

    _save_accounts_data(data)
    return True


def _apply_account_to_environment(account: Dict[str, Any]):
    """將帳戶設定持久化寫入 .env 並即時反映至 os.environ。"""
    env_path = REPO_ROOT / ".env"
    lines = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    auth_type = account.get("auth_type", "service_account")
    project_id = account.get("project_id", "")
    location = account.get("location", "us-central1")
    cred_file = account.get("credentials_file", "")
    api_key = account.get("api_key_raw", "")

    # 解析容器與本機路徑
    abs_cred_path = ""
    if cred_file:
        if Path(cred_file).is_absolute():
            abs_cred_path = cred_file
        else:
            # 檢查是否在容器內
            if Path("/workspace").is_dir():
                abs_cred_path = f"/workspace/{cred_file.lstrip('/')}"
            else:
                abs_cred_path = str(REPO_ROOT / cred_file)

    updates = {}
    if auth_type == "api_key":
        updates["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
        updates["GEMINI_API_KEY"] = api_key
        updates["GOOGLE_CLOUD_PROJECT"] = project_id or ""
        updates["GOOGLE_CLOUD_LOCATION"] = location or "us-central1"
        updates["GOOGLE_APPLICATION_CREDENTIALS"] = ""
    else:
        updates["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        updates["GOOGLE_CLOUD_PROJECT"] = project_id
        updates["GOOGLE_CLOUD_LOCATION"] = location or "us-central1"
        updates["GOOGLE_APPLICATION_CREDENTIALS"] = abs_cred_path
        updates["GEMINI_API_KEY"] = ""

    # 更新或追加到 .env
    new_lines = []
    seen = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                seen.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in seen:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # 更新當前執行時期的 os.environ
    for k, v in updates.items():
        if v:
            os.environ[k] = v
        elif k in os.environ:
            del os.environ[k]


def probe_single_model(model_id: str, model_type: str = "text") -> Dict[str, Any]:
    """極輕量、零延遲探測單一模型在當前憑證下是否啟用與可用。"""
    from aivideo.gemini_image import get_gemini_client_kwargs
    from aivideo.story_generator import resolve_text_model_name

    start_time = time.time()
    resolved_name = resolve_text_model_name(model_id) if model_type == "text" else model_id

    try:
        from google import genai
        from google.genai import types

        client_kwargs = get_gemini_client_kwargs(timeout_ms=10000, model=resolved_name)
        client = genai.Client(**client_kwargs)

        if model_type == "text":
            # 透過極小探針 (max_output_tokens=1) 驗證是否能正常呼叫
            resp = client.models.generate_content(
                model=resolved_name,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=1, temperature=0.0),
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "available",
                "message": "正常可用",
                "latency_ms": elapsed_ms,
            }
        else:
            # 生圖模型：透過 client.models.get 或元數據檢查存在性與授權
            try:
                m_info = client.models.get(model=resolved_name)
                elapsed_ms = int((time.time() - start_time) * 1000)
                return {
                    "status": "available",
                    "message": "生圖模型授權就緒",
                    "latency_ms": elapsed_ms,
                }
            except Exception as e:
                err_str = str(e)
                if "404" in err_str or "not found" in err_str.lower():
                    # 某些帳號在 global 端點支援
                    return {
                        "status": "available",
                        "message": "已配置 (呼叫時將自動路由可用地區)",
                        "latency_ms": int((time.time() - start_time) * 1000),
                    }
                raise e

    except Exception as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        err = str(exc)
        # 精確分類 Vertex AI 各種常見錯誤
        if "API has not been used" in err or "it is disabled" in err:
            return {
                "status": "disabled",
                "message": "未在 Google Cloud 專案中啟用 Vertex AI API",
                "latency_ms": elapsed_ms,
                "error_detail": err,
            }
        elif "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            return {
                "status": "quota_exceeded",
                "message": "配額暫時耗盡 (Quota Exceeded / 429)，需冷卻或提升配額",
                "latency_ms": elapsed_ms,
                "error_detail": err,
            }
        elif "PERMISSION_DENIED" in err or "403" in err:
            return {
                "status": "permission_denied",
                "message": "憑證缺少 Vertex AI User 或 Model 呼叫權限",
                "latency_ms": elapsed_ms,
                "error_detail": err,
            }
        elif "404" in err or "not found" in err.lower():
            return {
                "status": "unsupported",
                "message": "該專案或區域尚未開放此模型 (404 Not Found)",
                "latency_ms": elapsed_ms,
                "error_detail": err,
            }
        else:
            # 縮減長錯誤文字
            clean_err = err.split("\n")[0][:120]
            return {
                "status": "error",
                "message": f"檢測未通過: {clean_err}",
                "latency_ms": elapsed_ms,
                "error_detail": err,
            }


def check_all_models_status(force_refresh: bool = False) -> Dict[str, Any]:
    """檢測當前帳戶下所有文本與生圖模型的可用性與啟用狀態，並儲存快取。"""
    active_acc = get_active_account()
    now_ts = time.time()

    # 快取機制：60 秒內直接回傳快取結果，避免頻繁探測觸發配額
    if not force_refresh and CACHE_FILE.is_file():
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if now_ts - cached.get("timestamp", 0) < 60 and cached.get("account_id") == (active_acc.get("id") if active_acc else ""):
                return cached
        except Exception:
            pass

    models_report: Dict[str, Any] = {}

    for item in KNOWN_TEXT_MODELS:
        m_id = item["id"]
        res = probe_single_model(m_id, model_type="text")
        models_report[m_id] = {
            "name": item["name"],
            "type": "text",
            **res,
        }

    for item in KNOWN_IMAGE_MODELS:
        m_id = item["id"]
        res = probe_single_model(m_id, model_type="image")
        models_report[m_id] = {
            "name": item["name"],
            "type": "image",
            **res,
        }

    payload = {
        "account_id": active_acc.get("id") if active_acc else None,
        "account_name": active_acc.get("name") if active_acc else "未設定帳戶",
        "timestamp": now_ts,
        "checked_at": datetime.now().strftime("%H:%M:%S"),
        "models": models_report,
    }

    try:
        CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return payload
