from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS_DIR = REPO_ROOT / "assets" / "credentials"
TOKEN_FILE = CREDENTIALS_DIR / "youtube_token.json"
DEFAULT_CLIENT_SECRET_FILE = CREDENTIALS_DIR / "client_secret.json"
VERIFIER_FILE = CREDENTIALS_DIR / "oauth_verifier.json"

DEFAULT_REDIRECT_URI = "http://localhost:8000/api/v1/youtube/auth/callback"

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_client_secret_path() -> Optional[Path]:
    """獲取 Google OAuth 2.0 Client Secret 檔案路徑。"""
    env_path = os.getenv("YOUTUBE_CLIENT_SECRET_FILE")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    if DEFAULT_CLIENT_SECRET_FILE.is_file():
        return DEFAULT_CLIENT_SECRET_FILE
    root_secret = REPO_ROOT / "client_secret.json"
    if root_secret.is_file():
        return root_secret
    return None


def get_credentials():
    """取得或自動更新已授權的 Google OAuth 憑證物件。"""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        raise RuntimeError("未安裝 Google API 套件，請執行 pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")

    creds = None
    if TOKEN_FILE.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), YOUTUBE_SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as e:
            creds = None

    return creds


def get_auth_status() -> Dict[str, Any]:
    """檢查目前 YouTube API 的授權狀態與相關資訊。"""
    secret_path = get_client_secret_path()
    has_secret = secret_path is not None
    creds = None
    channel_info = None

    try:
        creds = get_credentials()
    except Exception:
        pass

    is_authenticated = creds is not None and creds.valid

    if is_authenticated:
        try:
            from googleapiclient.discovery import build
            youtube = build("youtube", "v3", credentials=creds)
            resp = youtube.channels().list(part="snippet", mine=True).execute()
            items = resp.get("items", [])
            if items:
                snippet = items[0].get("snippet", {})
                channel_info = {
                    "id": items[0].get("id"),
                    "title": snippet.get("title"),
                    "custom_url": snippet.get("customUrl"),
                    "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url"),
                }
        except Exception:
            pass

    return {
        "has_client_secret": has_secret,
        "client_secret_path": str(secret_path) if secret_path else None,
        "is_authenticated": is_authenticated,
        "channel": channel_info,
        "token_path": str(TOKEN_FILE) if TOKEN_FILE.is_file() else None,
    }


def _save_verifier(state: str, verifier: str) -> None:
    data = {}
    if VERIFIER_FILE.is_file():
        try:
            with open(VERIFIER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data[state] = verifier
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    with open(VERIFIER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _get_verifier(state: Optional[str] = None) -> Optional[str]:
    if not VERIFIER_FILE.is_file():
        return None
    try:
        with open(VERIFIER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if state and state in data:
            return data[state]
        if data:
            return list(data.values())[-1]
    except Exception:
        pass
    return None


def get_authorization_url(redirect_uri: Optional[str] = None) -> str:
    """產生 OAuth 2.0 使用者授權跳轉網址，並快取產生的 PKCE code_verifier。"""
    secret_path = get_client_secret_path()
    if not secret_path:
        raise ValueError(
            f"找不到 OAuth 憑證檔案，請先將 client_secret.json 放置於 {DEFAULT_CLIENT_SECRET_FILE}"
        )

    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise RuntimeError("未安裝 google-auth-oauthlib 套件")

    target_uri = redirect_uri or DEFAULT_REDIRECT_URI
    flow = Flow.from_client_secrets_file(
        str(secret_path),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=target_uri,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    if flow.code_verifier and state:
        _save_verifier(state, flow.code_verifier)
    return auth_url


def exchange_code_for_token(code: str, redirect_uri: Optional[str] = None, state: Optional[str] = None) -> Dict[str, Any]:
    """透過授權碼 (auth code) 與對應的 PKCE code_verifier 完成 Token 交換並儲存。"""
    secret_path = get_client_secret_path()
    if not secret_path:
        raise ValueError("找不到 client_secret.json")

    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise RuntimeError("未安裝 google-auth-oauthlib 套件")

    target_uri = redirect_uri or DEFAULT_REDIRECT_URI
    flow = Flow.from_client_secrets_file(
        str(secret_path),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=target_uri,
        state=state,
    )

    code_verifier = _get_verifier(state)
    if code_verifier:
        flow.code_verifier = code_verifier
        flow.fetch_token(code=code, code_verifier=code_verifier)
    else:
        flow.fetch_token(code=code)

    creds = flow.credentials

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    # 清除用過的暫存 verifier
    if VERIFIER_FILE.is_file():
        try:
            VERIFIER_FILE.unlink()
        except Exception:
            pass

    return get_auth_status()


def save_client_secret_content(content: str) -> None:
    """儲存傳入的 client_secret.json 內容。"""
    data = json.loads(content)
    if "installed" not in data and "web" not in data:
        raise ValueError("不合法的 Google OAuth client_secret.json 格式（需包含 installed 或 web 鍵值）")
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_CLIENT_SECRET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_youtube_chapters(job_dir: Path) -> str:
    """
    從分鏡與合成時間軸自動生成 YouTube 章節時間戳記 (例如 00:00 序幕)。
    YouTube 規範：第一幕必須從 00:00 開始，至少 3 個章節，每章節至少 10 秒。
    """
    chapters: List[str] = []
    film_json = job_dir / "compose" / "film.json"
    
    if film_json.is_file():
        try:
            with open(film_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            scenes_data = data.get("scenes", [])
            current_sec = 0.0
            for idx, sc in enumerate(scenes_data):
                dur = float(sc.get("duration", 6.0))
                title = sc.get("title") or f"第 {idx + 1} 幕"
                m, s = divmod(int(current_sec), 60)
                chapters.append(f"{m:02d}:{s:02d} {title}")
                current_sec += dur
            if len(chapters) >= 2:
                return "\n".join(chapters)
        except Exception:
            pass

    # 若無 film.json 則由 scenes 目錄掃描
    scenes_dir = job_dir / "scenes"
    if scenes_dir.is_dir():
        scene_dirs = sorted([d for d in scenes_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
        current_sec = 0.0
        for idx, sd in enumerate(scene_dirs):
            title = sd.name
            scene_yaml = sd / "scene.yaml"
            if scene_yaml.is_file():
                try:
                    import yaml
                    with open(scene_yaml, "r", encoding="utf-8") as f:
                        yd = yaml.safe_load(f)
                        if yd and yd.get("title"):
                            title = yd["title"]
                except Exception:
                    pass
            m, s = divmod(int(current_sec), 60)
            chapters.append(f"{m:02d}:{s:02d} {title}")
            current_sec += 6.0  # 預設每幕估計 6 秒
        if len(chapters) >= 2:
            return "\n".join(chapters)

    return ""


def upload_video_to_youtube(
    job_dir: Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: str = "unlisted",
    upload_subtitles: bool = True,
    upload_thumbnail: bool = True,
    old_video_id: Optional[str] = None,
    old_video_action: str = "private",
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """
    執行完整的 YouTube 上傳作業：
    1. 驗證影片檔案 (compose/film.mp4)
    2. 大檔案斷點續傳 (Resumable Upload，每次傳輸 10MB)
    3. 自動掛載繁體中文字幕 (compose/timeline.srt)
    4. 自動設定第一幕為影片縮圖封面 (scenes/001_*/current.png)
    """
    film_path = job_dir / "compose" / "film.mp4"
    if not film_path.is_file():
        raise FileNotFoundError(f"找不到成片檔案：{film_path}，請先執行影片合成")

    creds = get_credentials()
    if not creds or not creds.valid:
        raise PermissionError("尚未完成 YouTube 授權或授權已過期，請先於設定中登入 Google 帳號")

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise RuntimeError("未安裝 google-api-python-client 套件")

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],  # YouTube 限制標題 100 字元以內
            "description": description[:5000],  # 限制 5000 字元以內
            "tags": tags or ["AIVideo", "說書人", "紀錄片"],
            "categoryId": "27",  # 27 = Education (教育知識)
            "defaultLanguage": "zh-Hant",
            "defaultAudioLanguage": "zh-Hant",
        },
        "status": {
            "privacyStatus": privacy_status,  # private, unlisted, public
            "selfDeclaredMadeForKids": False,
        },
    }

    if progress_callback:
        progress_callback(0.05, "準備上傳成片至 YouTube...")

    # 10MB 分塊斷點續傳
    media = MediaFileUpload(
        str(film_path),
        mimetype="video/mp4",
        chunksize=10 * 1024 * 1024,
        resumable=True,
    )

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            pct = float(status.progress())
            # 上傳影片佔 5% ~ 85% 進度區間
            overall_pct = 0.05 + pct * 0.80
            if progress_callback:
                progress_callback(overall_pct, f"正在上傳影片... {int(pct * 100)}%")

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube 未回傳影片 ID，上傳可能失敗")

    video_url = f"https://youtu.be/{video_id}"
    studio_url = f"https://studio.youtube.com/video/{video_id}/edit"

    if progress_callback:
        progress_callback(0.88, f"影片上傳成功 (ID: {video_id})，正在處理附屬資源...")

    # 上傳字幕檔 (SRT)
    srt_uploaded = False
    srt_path = job_dir / "compose" / "timeline.srt"
    if upload_subtitles and srt_path.is_file():
        try:
            if progress_callback:
                progress_callback(0.90, "正在掛載繁體中文 SRT 字幕軌...")
            caption_body = {
                "snippet": {
                    "videoId": video_id,
                    "language": "zh-Hant",
                    "name": "中文（繁體）",
                    "isDraft": False,
                }
            }
            caption_media = MediaFileUpload(str(srt_path), mimetype="text/plain")
            youtube.captions().insert(
                part="snippet",
                body=caption_body,
                media_body=caption_media,
            ).execute()
            srt_uploaded = True
        except Exception as e:
            # 字幕失敗不中斷整體成功流程
            print(f"[YouTube] 上傳字幕警告：{e}")

    # 上傳封面縮圖 (Thumbnail)
    thumb_uploaded = False
    thumb_error_msg = None
    if upload_thumbnail:
        thumbnail_img = None
        # 1. 優先使用專為 YouTube 生成的高張力專屬縮圖
        dedicated_thumb = job_dir / "compose" / "thumbnail.png"
        if dedicated_thumb.is_file():
            thumbnail_img = dedicated_thumb
        else:
            # 2. 次選第一幕分鏡圖
            scenes_dir = job_dir / "scenes"
            if scenes_dir.is_dir():
                scene_dirs = sorted([d for d in scenes_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
                for sd in scene_dirs:
                    curr_img = sd / "current.png"
                    if curr_img.is_file():
                        thumbnail_img = curr_img
                        break
        
        if thumbnail_img and thumbnail_img.is_file():
            try:
                if progress_callback:
                    progress_callback(0.95, "正在設定影片封面縮圖...")
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_img), mimetype="image/png"),
                ).execute()
                thumb_uploaded = True
            except Exception as e:
                err_str = str(e)
                if "permissions to upload and set custom video thumbnails" in err_str.lower() or "403" in err_str:
                    thumb_error_msg = "該頻道尚未開通中階功能資格（需在 YouTube 工作室完成手機簡訊驗證才能啟用自訂封面縮圖）"
                else:
                    thumb_error_msg = err_str
                print(f"[YouTube] 上傳縮圖警告：{e}")

    # 處理上一版舊影片（若有指定且非 keep）
    if old_video_id and old_video_id != video_id:
        if old_video_action == "private":
            try:
                if progress_callback:
                    progress_callback(0.97, f"正在將舊版影片 ({old_video_id}) 設為私人下架...")
                youtube.videos().update(
                    part="status",
                    body={"id": old_video_id, "status": {"privacyStatus": "private"}},
                ).execute()
                print(f"[YouTube] 舊版影片 {old_video_id} 已成功設為私人下架")
            except Exception as e:
                print(f"[YouTube] 舊版影片下架警告：{e}")
        elif old_video_action == "delete":
            try:
                if progress_callback:
                    progress_callback(0.97, f"正在從 YouTube 徹底刪除舊版影片 ({old_video_id})...")
                youtube.videos().delete(id=old_video_id).execute()
                print(f"[YouTube] 舊版影片 {old_video_id} 已成功刪除")
            except Exception as e:
                print(f"[YouTube] 舊版影片刪除警告：{e}")

    if progress_callback:
        progress_callback(1.0, "YouTube 發布完成！")

    import datetime
    uploaded_at_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    publish_info = {
        "video_id": video_id,
        "video_url": video_url,
        "studio_url": studio_url,
        "title": title,
        "privacy_status": privacy_status,
        "has_subtitles": srt_uploaded,
        "has_thumbnail": thumb_uploaded,
        "thumbnail_error": thumb_error_msg,
        "uploaded_at": uploaded_at_str,
    }

    # 1. 持久化至 compose/youtube.json
    try:
        dest_dir = job_dir / "compose"
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(dest_dir / "youtube.json", "w", encoding="utf-8") as f:
            json.dump(publish_info, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[YouTube] 儲存 youtube.json 失敗：{e}")

    return publish_info


def get_job_youtube_info(job_dir: Path) -> Optional[Dict[str, Any]]:
    """讀取專案現有的 YouTube 發布記錄。"""
    yt_json = job_dir / "compose" / "youtube.json"
    if yt_json.is_file():
        try:
            with open(yt_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    job_yaml = job_dir / "job.yaml"
    if job_yaml.is_file():
        try:
            import yaml
            with open(job_yaml, "r", encoding="utf-8") as f:
                yd = yaml.safe_load(f) or {}
                if isinstance(yd.get("youtube"), dict):
                    return yd["youtube"]
        except Exception:
            pass

    return None


def update_existing_youtube_video(
    job_dir: Path,
    video_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    privacy_status: Optional[str] = None,
    upload_thumbnail: bool = True,
) -> Dict[str, Any]:
    """
    更新 YouTube 上已存在的影片資訊（例如補傳封面縮圖、更新標題說明），
    保留原有影片 ID、觀看次數與留言，不需要重新上傳影片。
    """
    creds = get_credentials()
    if not creds or not creds.valid:
        raise PermissionError("尚未完成 YouTube 授權或授權已過期，請先登入 Google 帳號")

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise RuntimeError("未安裝 google-api-python-client 套件")

    youtube = build("youtube", "v3", credentials=creds)

    # 1. 取得既有影片資訊
    resp = youtube.videos().list(part="snippet,status", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        raise FileNotFoundError(f"在 YouTube 上找不到指定影片 (ID: {video_id})")

    video_data = items[0]
    snippet = video_data.get("snippet", {})
    status = video_data.get("status", {})

    if title:
        snippet["title"] = title[:100]
    if description is not None:
        snippet["description"] = description[:5000]
    if tags:
        snippet["tags"] = tags
    if privacy_status:
        status["privacyStatus"] = privacy_status

    update_body = {
        "id": video_id,
        "snippet": snippet,
        "status": {
            "privacyStatus": status.get("privacyStatus", "unlisted"),
            "selfDeclaredMadeForKids": False,
        },
    }

    youtube.videos().update(
        part="snippet,status",
        body=update_body,
    ).execute()

    # 2. 補傳或更新封面縮圖 (Thumbnail)
    thumb_uploaded = False
    thumb_error = None
    if upload_thumbnail:
        thumbnail_img = job_dir / "compose" / "thumbnail.png"
        if not thumbnail_img.is_file():
            # 尋找第一幕
            scenes_dir = job_dir / "scenes"
            if scenes_dir.is_dir():
                for sd in sorted(scenes_dir.iterdir()):
                    if (sd / "current.png").is_file():
                        thumbnail_img = sd / "current.png"
                        break

        if thumbnail_img and thumbnail_img.is_file():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_img), mimetype="image/png"),
                ).execute()
                thumb_uploaded = True
            except Exception as e:
                err_str = str(e)
                if "permissions to upload and set custom video thumbnails" in err_str.lower() or "403" in err_str:
                    thumb_error = "該頻道尚未開通中階功能資格（需在 YouTube 工作室完成手機簡訊驗證才能啟用自訂封面縮圖）"
                else:
                    thumb_error = err_str
                print(f"[YouTube] 更新縮圖警告：{e}")

    # 更新本地記錄
    current_info = get_job_youtube_info(job_dir) or {}
    current_info["video_id"] = video_id
    current_info["title"] = snippet.get("title")
    current_info["has_thumbnail"] = thumb_uploaded
    current_info["thumbnail_error"] = thumb_error
    if privacy_status:
        current_info["privacy_status"] = privacy_status

    dest_dir = job_dir / "compose"
    dest_dir.mkdir(parents=True, exist_ok=True)
    with open(dest_dir / "youtube.json", "w", encoding="utf-8") as f:
        json.dump(current_info, f, indent=2, ensure_ascii=False)

    return current_info


def generate_youtube_metadata(job_dir: Path) -> Dict[str, Any]:
    """
    深度分析故事腳本與大綱，運用 YouTube 演算法推薦邏輯（高 CTR + 高完播率 + SEO），
    自動生成：
    1. 3 組極具吸引力的 YouTube 候選標題（懸念鉤子、巨大反差、數字對抗）
    2. 深度說明欄（前言 Hook、故事摘要、分鏡章節時間碼、Hashtags）
    3. 演算法高搜尋量標籤集 (Tags)
    4. 專屬縮圖英文提示詞 (Thumbnail Prompt)
    """
    from aivideo.commands.check import _load_dotenv
    _load_dotenv()
    from google import genai
    from google.genai import types
    from aivideo.gemini_image import get_gemini_client_kwargs
    from aivideo.story_generator import TEXT_MODELS

    # 讀取專案資料
    title = job_dir.name
    job_yaml = job_dir / "job.yaml"
    cfg = {}
    if job_yaml.is_file():
        try:
            import yaml
            with open(job_yaml, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                if cfg.get("title"):
                    title = cfg["title"]
        except Exception:
            pass

    outline_text = ""
    outline_path = job_dir / "outline.md"
    if outline_path.is_file():
        try:
            outline_text = outline_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    script_text = ""
    script_path = job_dir / "script.md"
    if script_path.is_file():
        try:
            script_text = script_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # 截取前 2500 字作為上下文以確保不爆 token
    context_text = f"專案標題：{title}\n\n大綱：\n{outline_text}\n\n故事腳本摘要：\n{script_text[:2500]}"

    system_instruction = """你是一位擁有百萬訂閱頻道的頂級 YouTube 營運總監與演算法專家。
你的任務是根據提供的說書人腳本，產出能最大化觸發 YouTube 推薦演算法（高 CTR 點擊率、高完播留存、強搜尋權重）的影片包裝中繼資料。

【標題設計原則（演算法權重最高）】
1. 嚴禁平淡如「介紹XXX」或「XXX的故事」，必須具備頂級說書專題的巨大吸引力與反差懸念（Hook）。
2. 常見演算法爆款句式：
   - 「當[主角]打開[秘密]：那件塵封的[關鍵物]，為何連[頂級機構]都在顫抖？」
   - 「[主角]曾坐擁[驚人事實]？揭秘[歷史事件]最荒謬的狂局！」
   - 「連[權威機構]都傻眼的驚天真相！[主角]究竟是如何做到的？」
3. 長度嚴格維持在 30 ~ 55 個繁體中文字元（手機端通知與首頁不被截斷的最佳長度）。
4. 請生成 3 組不同切入角度的高點擊率候選標題。

【說明欄原則】
1. 前 3 行（約 120 字）極度關鍵，必須在觀眾點擊「展開」前留下強烈懸念與搜尋關鍵詞。
2. 條理分明，包含故事簡介、核心反思、以及相關主題 Hashtags。

【縮圖提示詞 (Thumbnail Prompt)】
1. 必須為 100% 英文。
2. 專注於 YouTube 封面的視覺法則：單一鮮明主體、極致明暗對比 (Chiaroscuro / Rim light)、強烈戲劇衝突或懸疑張力、16:9 寬銀幕構圖。
3. 嚴禁文字與浮水印。

請嚴格輸出符合以下 JSON 格式的內容，不要包含額外 markdown 說明：
{
  "titles": ["標題選項1", "標題選項2", "標題選項3"],
  "best_title": "標題選項1",
  "hook_summary": "前言引子與懸念概要...",
  "tags": ["標籤1", "標籤2", "標籤3", ...約 10~15 個],
  "hashtags": ["#標籤1", "#標籤2", "#標籤3"],
  "thumbnail_prompt": "Cinematic, dramatic, high contrast 16:9 widescreen..."
}"""

    client_kwargs = get_gemini_client_kwargs()
    client = genai.Client(**client_kwargs)

    raw_json = None
    for model_name in TEXT_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=f"請為以下故事生成 YouTube 演算法最佳化中繼資料：\n\n{context_text}",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )
            raw_json = resp.text.strip()
            if raw_json:
                break
        except Exception as e:
            print(f"[YouTube Metadata] 模型 {model_name} 失敗：{e}")
            continue

    data = {}
    if raw_json:
        try:
            data = json.loads(raw_json)
        except Exception:
            pass

    titles = data.get("titles") or [title]
    best_title = data.get("best_title") or titles[0]
    hook_summary = data.get("hook_summary") or outline_text or "本影片講述一段不可思議的歷史傳奇。"
    tags = data.get("tags") or ["AIVideo", "說書人", "紀錄片", title]
    hashtags = data.get("hashtags") or ["#說書人", "#歷史秘辛", "#紀錄片"]

    # 組合結構化說明欄（已移除章節時間戳記與 AIVideo 流水線文字）
    desc_sections = [
        hook_summary.strip(),
        "",
        " ".join(hashtags),
    ]

    full_description = "\n".join(desc_sections).strip()

    # 提取適合縮圖封面的短短標題（4~8字，最具點擊吸引力）
    thumbnail_hook = data.get("thumbnail_hook") or title.split()[0] if title else "驚天真相"

    return {
        "titles": titles,
        "best_title": best_title,
        "thumbnail_hook": thumbnail_hook,
        "description": full_description,
        "tags": tags,
        "thumbnail_prompt": data.get("thumbnail_prompt") or f"Cinematic dramatic 16:9 widescreen shot of {title}, featuring giant bold yellow and white text '{thumbnail_hook}', intense dramatic lighting, 8k resolution, masterpiece",
    }


def generate_youtube_thumbnail(
    job_dir: Path,
    title: Optional[str] = None,
    custom_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    根據專案設定的畫風預設（Style Preset）、角色定裝參考圖（Visual Anchors）
    與使用者選定的影片標題，由 Gemini 3.1 Flash 專門繪製一張 16:9 封面縮圖，
    直接在畫面上生成醒目的黃白配色（Yellow and White）立體大字標題，儲存至 compose/thumbnail.png。
    """
    from aivideo.gemini_image import generate_image
    from aivideo.story_generator import load_style_presets, DEFAULT_STYLE_PRESETS
    from aivideo.visual_anchors import character_image_path, legacy_hero_path

    # 1. 讀取專案設定
    cfg = {}
    try:
        from aivideo.job_files import load_job_config

        cfg = load_job_config(job_dir)
    except Exception:
        pass

    chosen_title = (title or cfg.get("title") or job_dir.name).strip()
    img_cfg = cfg.get("image") if isinstance(cfg.get("image"), dict) else {}
    style_key = img_cfg.get("style") or cfg.get("style") or "otomo_katsuhiro"
    model_name = img_cfg.get("model") or cfg.get("image_model") or "gemini-3.1-flash-image"

    all_styles = load_style_presets()
    style_info = all_styles.get(style_key) or DEFAULT_STYLE_PRESETS.get(style_key, {})
    style_prefix = style_info.get("prefix") or ""

    # 2. 決定提示詞 (Prompt) 並注入黃白配色醒目標題文字指示
    text_instruction = (
        f'Features giant, ultra-bold, impactful stylized typography text: "{chosen_title}" '
        'prominently displayed in classic YouTube thumbnail fashion. '
        'Typography styling: bold sans-serif text rendered with vibrant golden-yellow and crisp pure-white color scheme '
        '(striking yellow and white letters), thick heavy black outline and deep 3D drop shadow for extreme contrast and high readability.'
    )

    prompt_body = (custom_prompt or "").strip()
    if not prompt_body:
        # 自動透過 Gemini 取得一個高張力縮圖背景與主體 prompt
        try:
            meta = generate_youtube_metadata(job_dir)
            prompt_body = meta.get("thumbnail_prompt", "")
        except Exception:
            pass

    if not prompt_body:
        prompt_body = (
            f"Epic YouTube thumbnail artwork, 16:9 widescreen, powerful visual hook featuring {chosen_title}, "
            "dramatic cinematic lighting, high contrast, rim light, tension and curiosity, hyper detailed, 8k."
        )

    from aivideo.style_prompt import compose_styled_prompt

    full_prompt = compose_styled_prompt(style_prefix, f"{prompt_body}，{text_instruction}")

    # 3. 收集角色定裝參考圖 (Maintain visual continuity)
    ref_images = []
    v_anchors = cfg.get("visual_anchors", {})
    if isinstance(v_anchors, dict) and v_anchors.get("use_image_reference", True):
        chars = v_anchors.get("characters", [])
        for ch in chars:
            if isinstance(ch, dict) and ch.get("id"):
                c_img = character_image_path(job_dir, ch["id"])
                if c_img.is_file():
                    ref_images.append((c_img, ch.get("name") or ch["id"]))
        if not ref_images:
            hero = legacy_hero_path(job_dir)
            if hero.is_file():
                ref_images.append((hero, "main character"))

    # 4. 生成並輸出到 compose/thumbnail.png
    dest_dir = job_dir / "compose"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "thumbnail.png"

    dest_path, used_model, used_seed = generate_image(
        prompt=full_prompt,
        dest=dest_path,
        aspect_ratio="16:9",
        model=model_name,
        ref_images=ref_images if ref_images else None,
    )

    import time
    ts = int(time.time())
    encoded_job = job_dir.name
    return {
        "success": True,
        "thumbnail_url": f"/media/jobs/{encoded_job}/compose/thumbnail.png?t={ts}",
        "prompt": full_prompt,
        "model": used_model,
        "seed": used_seed,
    }

